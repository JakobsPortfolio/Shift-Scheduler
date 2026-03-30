from datetime import datetime, timedelta
from collections import Counter
import random

DAY_ORDER = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

MIN_REST_HOURS = 11
MAX_CONSECUTIVE_DAYS = 5


def calculate_shift_hours(start, end):
    start_dt = datetime.strptime(start, "%H:%M")
    end_dt = datetime.strptime(end, "%H:%M")
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return (end_dt - start_dt).total_seconds() / 3600


def get_shift_datetimes(day, start, end):
    base_date = datetime(2025, 1, 6) + timedelta(days=DAY_ORDER[day])
    start_dt = datetime.combine(base_date.date(), datetime.strptime(start, "%H:%M").time())
    end_dt = datetime.combine(base_date.date(), datetime.strptime(end, "%H:%M").time())
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def has_enough_rest(emp_id, new_shift, last_shift_end_by_employee):
    if emp_id not in last_shift_end_by_employee:
        return True
    new_start, _ = get_shift_datetimes(new_shift["day"], new_shift["start"], new_shift["end"])
    last_end = last_shift_end_by_employee[emp_id]
    rest_hours = (new_start - last_end).total_seconds() / 3600
    return rest_hours >= MIN_REST_HOURS


def get_consecutive_days_count(emp_id, current_day, worked_days):
    current_index = DAY_ORDER[current_day]
    count = 0
    for i in range(current_index - 1, -1, -1):
        day_name = next(day for day, idx in DAY_ORDER.items() if idx == i)
        if day_name in worked_days[emp_id]:
            count += 1
        else:
            break
    return count


def would_exceed_consecutive_days(emp, shift_day, worked_days):
    consecutive_before = get_consecutive_days_count(emp["id"], shift_day, worked_days)
    return consecutive_before >= emp.get("max_consecutive_days", MAX_CONSECUTIVE_DAYS)


def count_days_worked_this_week(emp_id, worked_days):
    return len(worked_days[emp_id])


def count_shifts_this_week(emp_id, assignments):
    return sum(1 for a in assignments if a["employee_id"] == emp_id)


def is_weekend(day):
    return day in ["Saturday", "Sunday"]


def evaluate_employee_for_shift(
    emp,
    shift,
    availability,
    worked_days,
    hours_worked,
    last_shift_end_by_employee,
    assignments,
):
    if shift["type"] not in emp["skills"]:
        return False, "missing_skill"

    avail = next((a for a in availability if a["employee_id"] == emp["id"]), None)
    if not avail:
        return False, "no_availability_record"

    if shift["day"] not in avail["days"]:
        return False, "not_available_that_day"

    if shift["day"] in worked_days[emp["id"]]:
        return False, "already_has_shift_that_day"

    if not has_enough_rest(emp["id"], shift, last_shift_end_by_employee):
        return False, "not_enough_rest"

    if would_exceed_consecutive_days(emp, shift["day"], worked_days):
        return False, "max_consecutive_days_reached"

    shift_hours = calculate_shift_hours(shift["start"], shift["end"])
    if hours_worked[emp["id"]] + shift_hours > emp["max_hours_per_week"]:
        return False, "target_hours_exceeded"

    if emp.get("employment_type") == "part_time":
        max_shifts_per_week = emp.get("max_shifts_per_week", 2)
        if count_shifts_this_week(emp["id"], assignments) >= max_shifts_per_week:
            return False, "max_shifts_per_week_reached"

    return True, "eligible"


def get_employee_score(emp, shift, hours_worked, worked_days, week_seed):
    weekly_hours = hours_worked[emp["id"]]
    monthly_hours = emp.get("hours_worked_this_month", 0) + weekly_hours
    days_worked_this_week = count_days_worked_this_week(emp["id"], worked_days)

    monthly_gap = max(0, emp["monthly_target_hours"] - monthly_hours)
    preferred_max_days_worked = 7 - emp["preferred_days_off_per_week"]

    score = (
        weekly_hours * 2
        + monthly_hours * 1.5
        + days_worked_this_week * 8
        - monthly_gap * 0.2
    )

    if days_worked_this_week >= preferred_max_days_worked:
        score += 40

    last_week_shift_types = emp.get("last_week_shift_types", [])
    repeat_count = last_week_shift_types.count(shift["type"])
    score += repeat_count * 15

    if is_weekend(shift["day"]) and emp.get("last_week_worked_weekend", False):
        score += 20

    if shift["type"] in ["Breakfast", "Breakfast and Bakery", "Bakery", "Cafe and Breakfast Support"]:
        morning_repeat = sum(
            1 for s in last_week_shift_types
            if s in ["Breakfast", "Breakfast and Bakery", "Bakery", "Cafe and Breakfast Support"]
        )
        score += morning_repeat * 10

    if shift["type"] == "Closing Shift":
        closing_repeat = last_week_shift_types.count("Closing Shift")
        score += closing_repeat * 18

    if emp.get("employment_type") == "part_time":
        if shift["day"] in ["Monday", "Tuesday", "Wednesday", "Thursday"]:
            score += 18

        if shift["type"] in ["Breakfast", "Breakfast and Bakery", "Bakery", "Cafe and Breakfast Support"]:
            score += 12

        if shift["day"] in ["Saturday", "Sunday"]:
            score -= 8

        if weekly_hours < 8:
            score -= 3

    if emp.get("employment_type") == "full_time":
        if shift["day"] in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            score -= 3

    rotation_penalty = ((emp["id"] + week_seed) % 7) * 1.2
    score += rotation_penalty

    random.seed(f"{week_seed}-{emp['id']}-{shift['day']}-{shift['type']}")
    score += random.random()

    return score


def get_eligible_employees(
    shift,
    employees,
    availability,
    worked_days,
    hours_worked,
    last_shift_end_by_employee,
    week_seed,
    assignments,
):
    eligible = []

    for emp in employees:
        is_valid, _ = evaluate_employee_for_shift(
            emp,
            shift,
            availability,
            worked_days,
            hours_worked,
            last_shift_end_by_employee,
            assignments,
        )
        if is_valid:
            eligible.append(emp)

    eligible.sort(
        key=lambda e: get_employee_score(e, shift, hours_worked, worked_days, week_seed)
    )
    return eligible


def explain_unfilled_shift(
    shift,
    employees,
    availability,
    worked_days,
    hours_worked,
    last_shift_end_by_employee,
    assignments,
):
    reason_counts = {
        "missing_skill": 0,
        "no_availability_record": 0,
        "not_available_that_day": 0,
        "already_has_shift_that_day": 0,
        "not_enough_rest": 0,
        "max_consecutive_days_reached": 0,
        "target_hours_exceeded": 0,
        "max_shifts_per_week_reached": 0,
    }

    for emp in employees:
        is_valid, reason = evaluate_employee_for_shift(
            emp,
            shift,
            availability,
            worked_days,
            hours_worked,
            last_shift_end_by_employee,
            assignments,
        )
        if not is_valid:
            reason_counts[reason] += 1

    main_reason = max(reason_counts, key=reason_counts.get)

    readable_reasons = {
        "missing_skill": "Not enough employees have this shift skill",
        "no_availability_record": "Some employees have no availability data",
        "not_available_that_day": "Eligible employees are unavailable that day",
        "already_has_shift_that_day": "Eligible employees already have another shift that day",
        "not_enough_rest": "Eligible employees do not have enough rest before this shift",
        "max_consecutive_days_reached": "Eligible employees reached the maximum consecutive work days",
        "target_hours_exceeded": "Eligible employees would exceed their weekly max hours",
        "max_shifts_per_week_reached": "Eligible employees already reached their maximum shifts this week",
    }

    return {
        "main_reason_code": main_reason,
        "main_reason": readable_reasons[main_reason],
        "reason_breakdown": reason_counts,
    }


def build_summary(assignments, unfilled, employees, hours_worked):
    total_assigned = len(assignments)
    total_unfilled = len(unfilled)

    hours_summary = []
    for emp in employees:
        weekly_hours = hours_worked[emp["id"]]
        monthly_total = emp.get("hours_worked_this_month", 0) + weekly_hours
        hours_summary.append(
            {
                "employee": emp["name"],
                "weekly_hours": weekly_hours,
                "monthly_hours_after_schedule": monthly_total,
                "max_hours_per_week": emp["max_hours_per_week"],
            }
        )

    hours_summary.sort(key=lambda x: x["weekly_hours"], reverse=True)

    unfilled_reason_counter = Counter()
    unfilled_shift_counter = Counter()

    for item in unfilled:
        unfilled_reason_counter[item["reason_code"]] += 1
        unfilled_shift_counter[item["type"]] += 1

    return {
        "total_assigned_shifts": total_assigned,
        "total_unfilled_shifts": total_unfilled,
        "employees_at_or_above_40h": [
            h["employee"] for h in hours_summary if h["weekly_hours"] >= 40
        ],
        "top_unfilled_reasons": dict(unfilled_reason_counter),
        "top_unfilled_shift_types": dict(unfilled_shift_counter),
        "hours_summary": hours_summary,
    }


def extract_next_state(assignments, employees, hours_worked):
    assignments_by_employee = {}
    weekend_workers = set()

    for assignment in assignments:
        employee_name = assignment["employee"]
        assignments_by_employee.setdefault(employee_name, []).append(assignment["type"])

        if assignment["day"] in ["Saturday", "Sunday"]:
            weekend_workers.add(employee_name)

    next_state = {"employees": {}}

    for emp in employees:
        next_state["employees"][str(emp["id"])] = {
            "hours_worked_this_month": emp.get("hours_worked_this_month", 0) + hours_worked[emp["id"]],
            "last_week_shift_types": assignments_by_employee.get(emp["name"], []),
            "last_week_worked_weekend": emp["name"] in weekend_workers,
        }

    return next_state


def generate_schedule(data):
    employees = data["employees"]
    availability = data["availability"]
    shifts = data["shifts"]

    assignments = []
    unfilled = []

    hours_worked = {e["id"]: 0 for e in employees}
    worked_days = {e["id"]: set() for e in employees}
    last_shift_end_by_employee = {}

    week_start = data.get("week_start", "2026-03-16")
    try:
        week_seed = datetime.strptime(week_start, "%Y-%m-%d").isocalendar()[1]
    except Exception:
        week_seed = 1

    ordered_days = sorted({shift["day"] for shift in shifts}, key=lambda d: DAY_ORDER[d])

    for day in ordered_days:
        day_shifts = [shift for shift in shifts if shift["day"] == day]

        shifts_with_difficulty = []
        for shift in day_shifts:
            eligible = get_eligible_employees(
                shift,
                employees,
                availability,
                worked_days,
                hours_worked,
                last_shift_end_by_employee,
                week_seed,
                assignments,
            )
            shifts_with_difficulty.append((shift, len(eligible)))

        shifts_with_difficulty.sort(key=lambda x: (x[1], x[0]["start"]))

        for shift, _ in shifts_with_difficulty:
            eligible = get_eligible_employees(
                shift,
                employees,
                availability,
                worked_days,
                hours_worked,
                last_shift_end_by_employee,
                week_seed,
                assignments,
            )

            assigned = 0
            shift_hours = calculate_shift_hours(shift["start"], shift["end"])
            _, shift_end_dt = get_shift_datetimes(
                shift["day"], shift["start"], shift["end"]
            )

            for emp in eligible:
                if assigned >= shift["staff_needed"]:
                    break

                assignments.append(
                    {
                        "employee": emp["name"],
                        "employee_id": emp["id"],
                        "day": shift["day"],
                        "start": shift["start"],
                        "end": shift["end"],
                        "type": shift["type"],
                        "hours": shift_hours,
                    }
                )

                hours_worked[emp["id"]] += shift_hours
                worked_days[emp["id"]].add(shift["day"])
                last_shift_end_by_employee[emp["id"]] = shift_end_dt
                assigned += 1

            if assigned < shift["staff_needed"]:
                explanation = explain_unfilled_shift(
                    shift,
                    employees,
                    availability,
                    worked_days,
                    hours_worked,
                    last_shift_end_by_employee,
                    assignments,
                )

                unfilled.append(
                    {
                        "day": shift["day"],
                        "start": shift["start"],
                        "end": shift["end"],
                        "type": shift["type"],
                        "staff_needed": shift["staff_needed"],
                        "filled": assigned,
                        "missing": shift["staff_needed"] - assigned,
                        "reason": explanation["main_reason"],
                        "reason_code": explanation["main_reason_code"],
                        "reason_breakdown": explanation["reason_breakdown"],
                    }
                )

    assigned_employee_names = {a["employee"] for a in assignments}
    unassigned_employees = [
        e["name"] for e in employees if e["name"] not in assigned_employee_names
    ]

    summary = build_summary(assignments, unfilled, employees, hours_worked)
    next_state = extract_next_state(assignments, employees, hours_worked)

    return {
        "summary": summary,
        "assignments": assignments,
        "unfilled": unfilled,
        "hours_worked": hours_worked,
        "unassigned_employees": unassigned_employees,
        "next_state": next_state,
        "config": {
            "min_rest_hours": MIN_REST_HOURS,
            "max_consecutive_days": MAX_CONSECUTIVE_DAYS,
            "week_seed": week_seed,
        },
    }