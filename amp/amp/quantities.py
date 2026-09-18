"""Pure quantity rules shared by controllers and reports (no database access)."""
from math import isfinite


def number(value):
    value = float(value or 0)
    if not isfinite(value):
        raise ValueError("Quantity must be finite")
    return value


def completion(executed, budget):
    return min(100.0, max(0.0, number(executed) / number(budget) * 100)) if number(budget) > 0 else 0.0


def weighted_completion(rows):
    eligible = [r for r in rows if number(r.get("budget_qty")) > 0 and number(r.get("progress_weight")) > 0]
    weight = sum(number(r["progress_weight"]) for r in eligible)
    return round(sum(completion(r.get("executed_qty"), r["budget_qty"]) * number(r["progress_weight"]) for r in eligible) / weight, 2) if weight else 0.0


def unique_match(rows, item_code, uom=None, discipline=None):
    matches = [r for r in rows if r.get("item_code") == item_code
               and (not uom or r.get("uom") == uom)
               and (discipline is None or (r.get("discipline") or "") == discipline)]
    return matches[0] if len(matches) == 1 else None


def progress_values(budget, previous, period):
    executed = number(previous) + number(period)
    return dict(previous_qty=number(previous), period_qty=number(period), executed_qty=executed,
                remaining_qty=max(0, number(budget) - executed),
                overrun_qty=max(0, executed - number(budget)), percent_progress=completion(executed, budget))


def structural_progress_values(budget, fabrication_weight, erection_weight,
                               fabricated, erected, legacy_executed=0):
    """Return one physical-equivalent quantity and both structural stages.

    A tonne fabricated and the same tonne erected are two stages of one
    activity. Their quantities must therefore not be added together. The
    configured stage weights convert them into one completion value.
    """
    budget = number(budget)
    fabrication_weight = number(fabrication_weight)
    erection_weight = number(erection_weight)
    fabricated = number(fabricated)
    erected = number(erected)
    legacy_executed = number(legacy_executed)
    if fabrication_weight < 0 or erection_weight < 0 or round(fabrication_weight + erection_weight, 6) != 100:
        raise ValueError("Fabrication and erection weights must total 100")
    if erected > fabricated + 0.000001:
        raise ValueError("Erected quantity cannot exceed fabricated quantity")
    if budget <= 0:
        return dict(fabricated_qty=fabricated, erected_qty=erected, executed_qty=legacy_executed,
                    fabrication_percent=0, erection_percent=0, percent_progress=0,
                    remaining_qty=0, overrun_qty=max(0, legacy_executed))
    fabrication_percent = completion(fabricated, budget)
    erection_percent = completion(erected, budget)
    percent_progress = min(100, completion(legacy_executed, budget) +
        fabrication_percent * fabrication_weight / 100 + erection_percent * erection_weight / 100)
    executed = budget * percent_progress / 100
    return dict(fabricated_qty=fabricated, erected_qty=erected, executed_qty=executed,
                fabrication_percent=fabrication_percent, erection_percent=erection_percent,
                percent_progress=percent_progress, remaining_qty=max(0, budget - executed),
                overrun_qty=max(0, legacy_executed - budget))
