from typing import Dict, Any


def container_to_dict(c) -> Dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "shape": c.shape,
        "capacity": c.capacity,
        "orifice_diameter": c.orifice_diameter,
        "initial_water_level": c.initial_water_level,
        "shape_params": c.shape_params,
        "description": c.description
    }


def stage_to_dict(s) -> Dict[str, Any]:
    return {
        "id": s.id,
        "stage_order": s.stage_order,
        "stage_name": s.stage_name,
        "container_id": s.container_id,
        "container": container_to_dict(s.container) if s.container else None,
        "discharge_coefficient": s.discharge_coefficient,
        "is_refill_enabled": s.is_refill_enabled,
        "refill_trigger_level": s.refill_trigger_level,
        "refill_target_level": s.refill_target_level,
        "initial_level_override": s.initial_level_override,
        "orifice_diameter_override": s.orifice_diameter_override,
    }
