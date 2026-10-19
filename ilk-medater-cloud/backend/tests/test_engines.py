"""Moteurs de calcul : valeurs vérifiées à la main (aucune dépendance à la base)."""
import math

import pytest

from app.engines import DISCLAIMER
from app.engines.calcs import (AirRenewalIn, CableIn, ColumnIn, CoolingIn, DuctIn, FireIn, PowerBalanceIn, RainIn, VdiIn,
                               WaterIn, air_renewal, cable_drop, column, cold_water, cooling, duct, fire, power_balance,
                               rainwater, vdi)


def test_power_balance():
    r = power_balance(PowerBalanceIn(loads=[{"label": "Éclairage", "quantity": 100, "unit_power_w": 36, "ku": 1, "cos_phi": 1},
                                            {"label": "Prises", "quantity": 50, "unit_power_w": 200, "ku": 0.5, "cos_phi": 0.8}],
                                     ks=0.8, reserve=1.2))
    o = r["outputs"]
    assert o["p_installed_kw"] == 13.6
    # P = (3600 + 5000) × 0,8 = 6880 W ; Q = 5000 × 0,75 × 0,8 = 3000 var
    assert o["p_demand_kw"] == 6.88 and o["q_demand_kvar"] == 3.0
    s = math.hypot(6880, 3000)
    assert o["s_demand_kva"] == round(s / 1000, 2)
    assert o["current_a"] == round(s * 1.2 / (math.sqrt(3) * 400), 1)
    assert DISCLAIMER in r["warnings"]


def test_cable_drop():
    r = cable_drop(CableIn(power_w=20000, voltage_v=400, phases=3, cos_phi=0.85, length_m=100, section_mm2=10))
    ib = 20000 / (math.sqrt(3) * 400 * 0.85)
    du = (0.0225 * 100 / 10 * 0.85 + 0.08e-3 * 100 * math.sqrt(1 - 0.85 ** 2)) * ib
    assert r["outputs"]["design_current_a"] == round(ib, 2)
    assert r["outputs"]["drop_pct"] == round(100 * du / (400 / math.sqrt(3)), 2)
    # 6 mm² : ΔU ≈ 4,75 % (≤ 5 %) ; 4 mm² : ΔU ≈ 7,1 % → section minimale 6 mm²
    assert r["outputs"]["min_section_for_drop_mm2"] == 6


def test_cable_minimal_section_respects_limit():
    for limit in (3, 5):
        r = cable_drop(CableIn(power_w=20000, length_m=100, max_drop_pct=limit))["outputs"]
        smin = r["min_section_for_drop_mm2"]
        assert cable_drop(CableIn(power_w=20000, length_m=100, section_mm2=smin, max_drop_pct=limit))["outputs"]["drop_ok"]
        from app.engines.calcs import SECTIONS_MM2
        prev = SECTIONS_MM2[SECTIONS_MM2.index(smin) - 1]
        assert not cable_drop(CableIn(power_w=20000, length_m=100, section_mm2=prev, max_drop_pct=limit))["outputs"]["drop_ok"]


def test_cold_water():
    r = cold_water(WaterIn(fixtures={"lavabo": 10, "wc_reservoir": 10}))["outputs"]
    assert r["fixtures_count"] == 20 and r["base_flow_ls"] == 3.2
    y = 0.8 / math.sqrt(19)
    assert r["simultaneity_y"] == round(y, 3) and r["probable_flow_ls"] == round(3.2 * y, 3)
    dmin = math.sqrt(4 * 3.2 * y / 1000 / (math.pi * 1.5)) * 1000
    assert r["min_inner_diameter_mm"] == round(dmin, 1) and r["chosen_inner_diameter_mm"] == 26


def test_rainwater():
    assert rainwater(RainIn(area_m2=360, intensity_mm_h=100))["outputs"]["flow_ls"] == 10.0


def test_cooling():
    r = cooling(CoolingIn(floor_area_m2=100, walls=[{"u_w_m2k": 1, "area_m2": 50, "delta_t_k": 10}],
                          glazing=[{"area_m2": 10, "shgc": 0.5, "irradiance_w_m2": 400}], occupants=10,
                          lighting_w_m2=10, equipment_w_m2=10, fresh_air_m3h=250, outdoor_indoor_dt_k=10,
                          humidity_diff_g_kg=5, safety_factor=1.0))["outputs"]
    sens = 500 + 2000 + 750 + 1000 + 1000 + 0.34 * 250 * 10
    lat = 550 + 0.83 * 250 * 5
    assert r["sensible_w"] == round(sens) and r["latent_w"] == round(lat)
    assert r["total_kw"] == round((sens + lat) / 1000, 2)


def test_duct():
    r = duct(DuctIn(flow_m3h=1000, velocity_ms=5, length_m=10))["outputs"]
    assert r["theoretical_diameter_mm"] == round(math.sqrt(4 * 1000 / 3600 / 5 / math.pi) * 1000)  # 266 mm
    assert r["chosen_diameter_mm"] == 315
    v = 1000 / 3600 / (math.pi * 0.315 ** 2 / 4)
    re = v * 0.315 / 1.5e-5
    f = 0.25 / math.log10(0.09e-3 / (3.7 * 0.315) + 5.74 / re ** 0.9) ** 2
    assert r["linear_loss_pa_m"] == round(f / 0.315 * 1.2 * v ** 2 / 2, 3)
    assert 0.4 < r["linear_loss_pa_m"] < 0.7  # cohérent avec les abaques (~0,5 Pa/m pour Ø315 à 3,6 m/s)


def test_air_and_vdi_and_fire():
    assert air_renewal(AirRenewalIn(occupants=20, volume_m3=300, air_changes_per_h=2))["outputs"]["design_flow_m3h"] == 600
    v = vdi(VdiIn(workstations=40, wifi_area_m2=600, cameras=8))["outputs"]
    assert v["wifi_access_points"] == 4 and v["copper_ports"] == 92 and v["ports_with_reserve"] == 111 and v["switches"] == 3
    f = fire(FireIn(levels=[450, 150]))
    assert f["outputs"]["water_extinguishers_per_level"] == [3, 1]
    assert any("Détection" in w for w in f["warnings"])


def test_column():
    r = column(ColumnIn(floors=5, tributary_area_m2=16, g_kn_m2=6.5, q_kn_m2=2.5, seismic_zone="III"))["outputs"]
    g, q = 5 * 16 * 6.5, 5 * 16 * 2.5
    nu = 1.35 * g + 1.5 * q
    assert r["nu_elu_kn"] == round(nu, 1)
    alpha = 0.85 / 1.2
    br = nu / 1000 / (alpha * (25 / 1.35 + 0.01 * 400 / 1.15))
    assert r["br_required_cm2"] == round(br * 1e4)
    assert r["proposed_square_side_cm"] >= 30  # minimum zone III


def test_validation_rejects_absurd_inputs():
    with pytest.raises(ValueError):
        ColumnIn(floors=0, tributary_area_m2=10)
    with pytest.raises(ValueError):
        WaterIn(fixtures={"piscine": 1})
