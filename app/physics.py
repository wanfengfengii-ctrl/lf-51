import math
from typing import List, Dict, Tuple, Optional

GRAVITY = 9.81


def get_cross_sectional_area(shape: str, water_level: float, capacity: float, shape_params: Optional[str] = None) -> float:
    if shape == 'cylindrical':
        return capacity / max(capacity, 1e-6) * math.pi * 1.0
    elif shape == 'conical':
        ratio = water_level / capacity if capacity > 0 else 0
        return (ratio ** 2) * math.pi * 1.0
    elif shape == 'inverted_conical':
        ratio = 1 - (water_level / capacity) if capacity > 0 else 0
        return (ratio ** 2) * math.pi * 1.0 + 0.1
    elif shape == 'spherical':
        r = (capacity * 3 / (4 * math.pi)) ** (1/3) if capacity > 0 else 1
        h = water_level
        if h >= 2 * r:
            h = 2 * r
        return math.pi * h * (2 * r - h)
    else:
        return 1.0


def get_orifice_area(orifice_diameter: float) -> float:
    return math.pi * (orifice_diameter / 2) ** 2


def calculate_flow_rate(water_level: float, orifice_diameter: float,
                        shape: str, capacity: float, shape_params: Optional[str] = None,
                        discharge_coefficient: float = 0.6) -> float:
    if water_level <= 0:
        return 0.0
    orifice_area = get_orifice_area(orifice_diameter)
    velocity = discharge_coefficient * math.sqrt(2 * GRAVITY * water_level)
    return orifice_area * velocity


def calculate_water_level_drop_rate(water_level: float, orifice_diameter: float,
                                     shape: str, capacity: float, shape_params: Optional[str] = None) -> float:
    if water_level <= 0:
        return 0.0
    container_area = get_cross_sectional_area(shape, water_level, capacity, shape_params)
    if container_area <= 0:
        return 0.0
    flow_rate = calculate_flow_rate(water_level, orifice_diameter, shape, capacity, shape_params)
    return flow_rate / container_area


def simulate_water_curve(initial_water_level: float, orifice_diameter: float,
                         shape: str, capacity: float, shape_params: Optional[str] = None,
                         time_step: float = 0.1, max_time: float = 100000.0) -> List[Tuple[float, float]]:
    results = []
    current_level = initial_water_level
    current_time = 0.0
    results.append((current_time, current_level))

    while current_level > 0.001 and current_time < max_time:
        drop_rate = calculate_water_level_drop_rate(current_level, orifice_diameter, shape, capacity, shape_params)
        actual_step = min(time_step, current_level / max(drop_rate, 1e-10) if drop_rate > 0 else time_step)
        current_level -= drop_rate * actual_step
        current_time += actual_step
        if current_level < 0:
            current_level = 0
        results.append((round(current_time, 4), round(current_level, 6)))

    return results


def find_time_for_water_level(target_level: float, curve: List[Tuple[float, float]]) -> Optional[float]:
    if not curve:
        return None

    if curve[0][1] <= target_level:
        return curve[0][0]

    for i in range(1, len(curve)):
        prev_time, prev_level = curve[i - 1]
        curr_time, curr_level = curve[i]

        if prev_level >= target_level >= curr_level:
            if prev_level == curr_level:
                return prev_time
            ratio = (prev_level - target_level) / (prev_level - curr_level)
            return prev_time + ratio * (curr_time - prev_time)

    return curve[-1][0]


def find_water_level_for_time(target_time: float, curve: List[Tuple[float, float]]) -> Optional[float]:
    if not curve:
        return None

    if target_time <= curve[0][0]:
        return curve[0][1]

    for i in range(1, len(curve)):
        prev_time, prev_level = curve[i - 1]
        curr_time, curr_level = curve[i]

        if prev_time <= target_time <= curr_time:
            if prev_time == curr_time:
                return prev_level
            ratio = (target_time - prev_time) / (curr_time - prev_time)
            return prev_level + ratio * (curr_level - prev_level)

    return curve[-1][1]


def generate_scale_marks(scale_count: int, time_interval: float, initial_water_level: float,
                         orifice_diameter: float, shape: str, capacity: float,
                         shape_params: Optional[str] = None, error_threshold: float = 5.0
                         ) -> List[Dict]:
    curve = simulate_water_curve(initial_water_level, orifice_diameter, shape, capacity, shape_params)
    marks = []

    for i in range(scale_count + 1):
        theoretical_time = i * time_interval
        water_level = find_water_level_for_time(theoretical_time, curve)

        if water_level is not None:
            actual_time = find_time_for_water_level(water_level, curve) or theoretical_time
        else:
            actual_time = theoretical_time
            water_level = 0

        error = abs(actual_time - theoretical_time)

        marks.append({
            'scale_index': i,
            'theoretical_time': theoretical_time,
            'estimated_time': actual_time,
            'water_level': water_level,
            'error': error,
            'exceeds_threshold': error > error_threshold
        })

    return marks


def calculate_average_error(marks: List[Dict]) -> float:
    if not marks:
        return 0.0
    return sum(m['error'] for m in marks) / len(marks)


def calculate_max_error(marks: List[Dict]) -> float:
    if not marks:
        return 0.0
    return max(m['error'] for m in marks)


def interpolate_experimental_data(data_points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if len(data_points) < 2:
        return data_points

    sorted_points = sorted(data_points, key=lambda x: x[0])
    result = []
    for i in range(len(sorted_points) - 1):
        t1, l1 = sorted_points[i]
        t2, l2 = sorted_points[i + 1]
        steps = max(2, int((t2 - t1) / 0.5))
        for j in range(steps):
            ratio = j / steps
            t = t1 + ratio * (t2 - t1)
            l = l1 + ratio * (l2 - l1)
            result.append((round(t, 4), round(l, 6)))
    result.append(sorted_points[-1])
    return result
