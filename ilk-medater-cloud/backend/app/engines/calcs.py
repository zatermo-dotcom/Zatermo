"""Moteurs de pré-dimensionnement par spécialité (MEP 01 à 06, génie civil).

Toutes les valeurs « de référence » proposées par défaut sont marquées « à confirmer » : le bureau d'études
doit les remplacer par celles du référentiel contractuel applicable au projet.
"""
import math
from typing import Literal, Optional

from pydantic import BaseModel, Field

from . import Engine, result

# =============================================================== MEP 01 — Courant fort
SECTIONS_MM2 = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300]


class Load(BaseModel):
    label: str = Field(max_length=120)
    quantity: int = Field(ge=1, le=100000)
    unit_power_w: float = Field(gt=0, le=5e6)
    ku: float = Field(default=1.0, gt=0, le=1, description="Facteur d'utilisation")
    cos_phi: float = Field(default=0.9, gt=0, le=1)


class PowerBalanceIn(BaseModel):
    loads: list[Load] = Field(min_length=1, max_length=500)
    ks: float = Field(default=0.8, gt=0, le=1, description="Coefficient de simultanéité global")
    reserve: float = Field(default=1.2, ge=1, le=2, description="Coefficient d'extension (à confirmer)")
    voltage_v: float = Field(default=400, gt=0)
    phases: Literal[1, 3] = 3


def power_balance(d: PowerBalanceIn) -> dict:
    p_inst = sum(l.quantity * l.unit_power_w for l in d.loads)
    p_used = sum(l.quantity * l.unit_power_w * l.ku for l in d.loads)
    q_used = sum(l.quantity * l.unit_power_w * l.ku * math.tan(math.acos(l.cos_phi)) for l in d.loads)
    p = p_used * d.ks
    q = q_used * d.ks
    s = math.hypot(p, q)
    s_res = s * d.reserve
    current = s_res / (math.sqrt(3) * d.voltage_v) if d.phases == 3 else s_res / d.voltage_v
    rows = [{"label": l.label, "p_installed_w": l.quantity * l.unit_power_w,
             "p_used_w": round(l.quantity * l.unit_power_w * l.ku, 1)} for l in d.loads]
    return result({
        "p_installed_kw": round(p_inst / 1000, 2), "p_demand_kw": round(p / 1000, 2),
        "q_demand_kvar": round(q / 1000, 2), "s_demand_kva": round(s / 1000, 2),
        "s_with_reserve_kva": round(s_res / 1000, 2), "global_cos_phi": round(p / s, 3) if s else None,
        "current_a": round(current, 1), "detail": rows,
    }, ["Coefficients ku/ks et réserve à justifier selon la nature des locaux et le référentiel retenu."])


class CableIn(BaseModel):
    power_w: float = Field(gt=0, le=5e6)
    voltage_v: float = Field(default=400, gt=0, description="Tension entre phases (tri) ou phase-neutre (mono)")
    phases: Literal[1, 3] = 3
    cos_phi: float = Field(default=0.85, gt=0, le=1)
    length_m: float = Field(gt=0, le=5000)
    section_mm2: Optional[float] = Field(default=None, gt=0)
    material: Literal["cuivre", "aluminium"] = "cuivre"
    max_drop_pct: float = Field(default=5.0, gt=0, le=20, description="3 % éclairage / 5 % autres usages (à confirmer)")


def cable_drop(d: CableIn) -> dict:
    # Méthode simplifiée NF C 15-100 / CEI 60364-5-52 (annexe G) :
    # ΔU = b (ρ1 L/S cosφ + λ L sinφ) Ib ; ΔU% = 100 ΔU / U0  (U0 tension phase-neutre)
    rho = 0.0225 if d.material == "cuivre" else 0.036  # Ω·mm²/m, conducteur en service
    lam = 0.08e-3  # Ω/m
    b = 1 if d.phases == 3 else 2
    u0 = d.voltage_v / math.sqrt(3) if d.phases == 3 else d.voltage_v
    ib = d.power_w / (math.sqrt(3) * d.voltage_v * d.cos_phi) if d.phases == 3 else d.power_w / (d.voltage_v * d.cos_phi)
    sin_phi = math.sqrt(1 - d.cos_phi ** 2)

    def drop(section):
        du = b * (rho * d.length_m / section * d.cos_phi + lam * d.length_m * sin_phi) * ib
        return du, 100 * du / u0

    minimal = next((sec for sec in SECTIONS_MM2 if drop(sec)[1] <= d.max_drop_pct), None)
    out = {"design_current_a": round(ib, 2), "min_section_for_drop_mm2": minimal, "u0_v": round(u0, 1)}
    warnings = ["Courant admissible (mode de pose, température, groupement), protection et sélectivité non vérifiés par ce moteur."]
    if d.section_mm2:
        du, pct = drop(d.section_mm2)
        out.update({"section_mm2": d.section_mm2, "drop_v": round(du, 2), "drop_pct": round(pct, 2),
                    "drop_ok": pct <= d.max_drop_pct})
    if minimal is None:
        warnings.append("Aucune section normalisée jusqu'à 300 mm² ne respecte la chute de tension : revoir le tracé ou la tension.")
    return result(out, warnings)


# =============================================================== MEP 02 — Courants faibles
class VdiIn(BaseModel):
    workstations: int = Field(ge=0, le=20000)
    outlets_per_workstation: int = Field(default=2, ge=1, le=8)
    wifi_area_m2: float = Field(default=0, ge=0)
    m2_per_access_point: float = Field(default=150, gt=0, description="Couverture par borne (à confirmer par étude radio)")
    cameras: int = Field(default=0, ge=0)
    access_points_extra: int = Field(default=0, ge=0)
    reserve_pct: float = Field(default=20, ge=0, le=100)
    ports_per_switch: int = Field(default=48, ge=8, le=96)
    max_link_m: float = Field(default=90, description="Lien permanent cuivre (classe E/EA)")
    longest_run_m: Optional[float] = Field(default=None, ge=0)


def vdi(d: VdiIn) -> dict:
    aps = math.ceil(d.wifi_area_m2 / d.m2_per_access_point) if d.wifi_area_m2 else 0
    ports = d.workstations * d.outlets_per_workstation + aps + d.cameras + d.access_points_extra
    ports_res = math.ceil(ports * (1 + d.reserve_pct / 100))
    warnings = []
    if d.longest_run_m and d.longest_run_m > d.max_link_m:
        warnings.append(f"Liaison la plus longue {d.longest_run_m} m > {d.max_link_m} m : prévoir un local technique d'étage supplémentaire ou de la fibre.")
    return result({"wifi_access_points": aps, "copper_ports": ports, "ports_with_reserve": ports_res,
                   "switches": math.ceil(ports_res / d.ports_per_switch),
                   "poe_ports": aps + d.cameras + d.access_points_extra}, warnings)


# =============================================================== MEP 03 — Incendie
class FireIn(BaseModel):
    levels: list[float] = Field(min_length=1, max_length=100, description="Surface de chaque niveau (m²)")
    m2_per_extinguisher: float = Field(default=200, gt=0, description="Règle usuelle à confirmer (Protection civile)")
    max_travel_m: float = Field(default=15, gt=0)
    detector_coverage_m2: Optional[float] = Field(default=None, gt=0, description="Surface surveillée par détecteur, selon hauteur sous plafond et norme")
    special_risk_rooms: int = Field(default=0, ge=0, description="Locaux à risque particulier (chaufferie, TGBT…)")


def fire(d: FireIn) -> dict:
    per_level = [max(1, math.ceil(a / d.m2_per_extinguisher)) for a in d.levels]
    out = {"water_extinguishers_per_level": per_level, "water_extinguishers_total": sum(per_level),
           "co2_extinguishers_special_rooms": d.special_risk_rooms,
           "max_travel_distance_m": d.max_travel_m}
    warnings = ["Classement de l'établissement, exigences de la Protection civile et du règlement de sécurité applicable à confirmer.",
                "Vérifier sur plan que tout point est à moins de la distance maximale d'un extincteur."]
    if d.detector_coverage_m2:
        dets = [math.ceil(a / d.detector_coverage_m2) for a in d.levels]
        out.update({"detectors_per_level": dets, "detectors_total": sum(dets)})
    else:
        warnings.append("Détection : renseigner la surface surveillée par détecteur (dépend de la hauteur et du type de détecteur).")
    return result(out, warnings)


# =============================================================== MEP 04 — Plomberie
BASE_FLOWS_LS = {  # Débits de base par appareil (l/s) — valeurs usuelles DTU 60.11, à confirmer
    "evier": 0.20, "lavabo": 0.20, "lave_mains": 0.10, "douche": 0.20, "baignoire": 0.33, "bidet": 0.20,
    "wc_reservoir": 0.12, "urinoir": 0.15, "lave_linge": 0.20, "lave_vaisselle": 0.10, "poste_eau": 0.33,
}
INNER_DIAMETERS_MM = [10, 12, 14, 16, 20, 26, 33, 40, 50, 66, 80, 100, 125, 150]


class WaterIn(BaseModel):
    fixtures: dict[Literal[tuple(BASE_FLOWS_LS)], int] = Field(min_length=1)  # type: ignore[valid-type]
    max_velocity_ms: float = Field(default=1.5, gt=0.2, le=3)


def cold_water(d: WaterIn) -> dict:
    x = sum(n for n in d.fixtures.values() if n > 0)
    q_base = sum(BASE_FLOWS_LS[k] * n for k, n in d.fixtures.items())
    y = 1.0 if x <= 1 else min(1.0, 0.8 / math.sqrt(x - 1))
    q = q_base * y
    d_min = math.sqrt(4 * (q / 1000) / (math.pi * d.max_velocity_ms)) * 1000
    chosen = next((di for di in INNER_DIAMETERS_MM if di >= d_min), None)
    v = (q / 1000) / (math.pi * (chosen / 1000) ** 2 / 4) if chosen else None
    return result({"fixtures_count": x, "base_flow_ls": round(q_base, 3), "simultaneity_y": round(y, 3),
                   "probable_flow_ls": round(q, 3), "min_inner_diameter_mm": round(d_min, 1),
                   "chosen_inner_diameter_mm": chosen, "velocity_ms": round(v, 2) if v else None},
                  ["Coefficient y = 0,8/√(x−1) (logements/locaux courants) ; usages collectifs intensifs : méthode spécifique.",
                   "Pertes de charge et pression disponible au point le plus défavorisé non vérifiées."])


class RainIn(BaseModel):
    area_m2: float = Field(gt=0)
    runoff_coefficient: float = Field(default=1.0, gt=0, le=1)
    intensity_mm_h: float = Field(gt=0, le=500, description="Intensité pluviométrique de projet du site (donnée locale obligatoire)")


def rainwater(d: RainIn) -> dict:
    q = d.runoff_coefficient * d.intensity_mm_h * d.area_m2 / 3600  # l/s
    return result({"flow_ls": round(q, 2)}, ["Intensité de projet à justifier par les données pluviométriques du site."])


# =============================================================== MEP 05 — HVAC
class Wall(BaseModel):
    label: str = Field(default="", max_length=80)
    u_w_m2k: float = Field(gt=0, le=10)
    area_m2: float = Field(gt=0)
    delta_t_k: float = Field(ge=-30, le=40)


class Glazing(BaseModel):
    area_m2: float = Field(gt=0)
    shgc: float = Field(gt=0, le=1)
    irradiance_w_m2: float = Field(ge=0, le=1200, description="Rayonnement de projet sur la façade (donnée du site)")


class CoolingIn(BaseModel):
    floor_area_m2: float = Field(gt=0)
    walls: list[Wall] = Field(default_factory=list)
    glazing: list[Glazing] = Field(default_factory=list)
    occupants: int = Field(default=0, ge=0)
    sensible_w_per_person: float = Field(default=75, ge=0)
    latent_w_per_person: float = Field(default=55, ge=0)
    lighting_w_m2: float = Field(default=10, ge=0)
    equipment_w_m2: float = Field(default=15, ge=0)
    fresh_air_m3h: float = Field(default=0, ge=0)
    outdoor_indoor_dt_k: float = Field(default=0, ge=-30, le=30)
    humidity_diff_g_kg: float = Field(default=0, ge=0, le=30)
    safety_factor: float = Field(default=1.1, ge=1, le=1.5)


def cooling(d: CoolingIn) -> dict:
    cond = sum(w.u_w_m2k * w.area_m2 * w.delta_t_k for w in d.walls)
    solar = sum(g.area_m2 * g.shgc * g.irradiance_w_m2 for g in d.glazing)
    ppl_s = d.occupants * d.sensible_w_per_person
    ppl_l = d.occupants * d.latent_w_per_person
    light = d.lighting_w_m2 * d.floor_area_m2
    equip = d.equipment_w_m2 * d.floor_area_m2
    vent_s = 0.34 * d.fresh_air_m3h * d.outdoor_indoor_dt_k   # 0,34 = ρ·cp/3600
    vent_l = 0.83 * d.fresh_air_m3h * d.humidity_diff_g_kg    # 0,83 = ρ·Lv/3600 (Δw en g/kg)
    sens = cond + solar + ppl_s + light + equip + vent_s
    lat = ppl_l + vent_l
    total = (sens + lat) * d.safety_factor
    return result({
        "conduction_w": round(cond), "solar_w": round(solar), "people_sensible_w": round(ppl_s),
        "people_latent_w": round(ppl_l), "lighting_w": round(light), "equipment_w": round(equip),
        "ventilation_sensible_w": round(vent_s), "ventilation_latent_w": round(vent_l),
        "sensible_w": round(sens), "latent_w": round(lat), "total_kw": round(total / 1000, 2),
        "total_tr": round(total / 3517, 2), "total_btu_h": round(total * 3.41214),
        "w_per_m2": round(total / d.floor_area_m2, 1)},
        ["Méthode en régime permanent simplifiée (sans inertie ni décalage horaire) : bilan dynamique requis pour l'étude d'exécution.",
         "Conditions extérieures de base et rayonnement à prendre dans les données climatiques du site."])


# =============================================================== MEP 06 — Aéraulique
ROUND_DUCTS_MM = [100, 125, 160, 200, 250, 315, 355, 400, 450, 500, 560, 630, 710, 800, 900, 1000, 1120, 1250]


class DuctIn(BaseModel):
    flow_m3h: float = Field(gt=0, le=500000)
    velocity_ms: float = Field(default=5.0, gt=0.5, le=20)
    length_m: float = Field(default=10, gt=0)
    singular_losses_zeta: float = Field(default=0, ge=0, le=100, description="Somme des coefficients ζ")
    roughness_mm: float = Field(default=0.09, gt=0, le=5)
    rectangular_aspect: Optional[float] = Field(default=None, ge=1, le=8)


def duct(d: DuctIn) -> dict:
    rho, nu = 1.2, 1.5e-5
    q = d.flow_m3h / 3600
    area = q / d.velocity_ms
    d_th = math.sqrt(4 * area / math.pi)
    chosen = next((x for x in ROUND_DUCTS_MM if x / 1000 >= d_th), ROUND_DUCTS_MM[-1])
    dm = chosen / 1000
    v = q / (math.pi * dm ** 2 / 4)
    re = v * dm / nu
    f = 0.25 / (math.log10(d.roughness_mm / 1000 / (3.7 * dm) + 5.74 / re ** 0.9)) ** 2  # Swamee-Jain
    dyn = rho * v ** 2 / 2
    dp_m = f / dm * dyn
    out = {"theoretical_diameter_mm": round(d_th * 1000), "chosen_diameter_mm": chosen, "velocity_ms": round(v, 2),
           "reynolds": round(re), "friction_factor": round(f, 4), "linear_loss_pa_m": round(dp_m, 3),
           "linear_loss_pa": round(dp_m * d.length_m, 1), "singular_loss_pa": round(d.singular_losses_zeta * dyn, 1),
           "total_loss_pa": round(dp_m * d.length_m + d.singular_losses_zeta * dyn, 1)}
    if d.rectangular_aspect:
        h = math.sqrt(area / d.rectangular_aspect)
        w = h * d.rectangular_aspect
        out["rectangular_mm"] = {"width": round(w * 1000), "height": round(h * 1000)}
    warnings = [] if chosen / 1000 >= d_th else ["Débit supérieur à la plus grande gaine ronde du catalogue : prévoir plusieurs réseaux."]
    return result(out, warnings + ["Vérifier niveaux sonores et vitesses admissibles selon les locaux desservis."])


class AirRenewalIn(BaseModel):
    occupants: int = Field(default=0, ge=0)
    m3h_per_person: float = Field(default=25, ge=0, description="Débit hygiénique par personne (à confirmer selon le texte applicable)")
    volume_m3: float = Field(default=0, ge=0)
    air_changes_per_h: float = Field(default=0, ge=0)


def air_renewal(d: AirRenewalIn) -> dict:
    by_people = d.occupants * d.m3h_per_person
    by_ach = d.volume_m3 * d.air_changes_per_h
    return result({"by_occupancy_m3h": round(by_people), "by_air_changes_m3h": round(by_ach),
                   "design_flow_m3h": round(max(by_people, by_ach))})


# =============================================================== Génie civil
class ColumnIn(BaseModel):
    floors: int = Field(ge=1, le=60)
    tributary_area_m2: float = Field(gt=0, le=200)
    g_kn_m2: float = Field(default=6.5, gt=0, le=30, description="Charges permanentes par plancher (à justifier)")
    q_kn_m2: float = Field(default=2.5, ge=0, le=30, description="Charges d'exploitation (selon usage, à justifier)")
    extra_g_kn: float = Field(default=0, ge=0, description="Poids propres complémentaires (poteaux, murs…)")
    fc28_mpa: float = Field(default=25, ge=16, le=60)
    fe_mpa: float = Field(default=400, ge=235, le=600)
    slenderness: float = Field(default=35, gt=0, le=50)
    steel_ratio: float = Field(default=0.01, ge=0.002, le=0.04)
    seismic_zone: Literal["0", "I", "IIa", "IIb", "III"] = "IIa"


def column(d: ColumnIn) -> dict:
    g = d.floors * d.tributary_area_m2 * d.g_kn_m2 + d.extra_g_kn
    q = d.floors * d.tributary_area_m2 * d.q_kn_m2
    nu = 1.35 * g + 1.5 * q  # kN, ELU
    alpha = 0.85 / (1 + 0.2 * (d.slenderness / 35) ** 2)
    capacity = alpha * (d.fc28_mpa / (0.9 * 1.5) + d.steel_ratio * d.fe_mpa / 1.15)  # MPa = MN/m²
    br = (nu / 1000) / capacity  # m²
    side = math.sqrt(br) + 0.02
    rpa_min = {"0": 0.25, "I": 0.25, "IIa": 0.25, "IIb": 0.30, "III": 0.30}[d.seismic_zone]
    proposed = max(math.ceil(side * 20) / 20, rpa_min)  # arrondi au 5 cm
    return result({"g_kn": round(g, 1), "q_kn": round(q, 1), "nu_elu_kn": round(nu, 1), "alpha": round(alpha, 3),
                   "br_required_cm2": round(br * 1e4), "square_side_required_cm": round(side * 100, 1),
                   "rpa_min_side_cm": rpa_min * 100, "proposed_square_side_cm": round(proposed * 100)},
                  ["Formule de compression centrée de type CBA 93 / BAEL : Nu ≤ α [Br·fc28/(0,9·γb) + A·fe/γs].",
                   "Dimension minimale sismique selon zone (RPA 99 version 2003) à vérifier, ainsi que l'effort normal réduit et le ferraillage.",
                   "Descente de charges simplifiée par surface d'influence ; vérifier les charges réelles par niveau."])


ENGINES = {e.code: e for e in [
    Engine("cfo.power_balance", "Bilan de puissance", "CFO", "1.0", PowerBalanceIn, power_balance,
           "P = Σ q·Pu·ku × ks ; Q = Σ P·tanφ × ks ; S = √(P²+Q²) × réserve ; I = S/(√3·U)"),
    Engine("cfo.cable_drop", "Chute de tension et section", "CFO", "1.0", CableIn, cable_drop,
           "ΔU = b(ρ1·L/S·cosφ + λ·L·sinφ)·Ib ; ΔU% = 100·ΔU/U0", ["NF C 15-100 / CEI 60364-5-52 (méthode simplifiée)"]),
    Engine("cfa.vdi", "Dimensionnement VDI", "CFA", "1.0", VdiIn, vdi, "Ports = postes×prises + bornes Wi-Fi + caméras ; réserve ; commutateurs"),
    Engine("fire.extinguishers", "Extincteurs et détection", "FIRE", "1.0", FireIn, fire, "N = max(1, ⌈S/Sref⌉) par niveau"),
    Engine("plumb.cold_water", "Débit probable et diamètre EF", "PLUMB", "1.0", WaterIn, cold_water,
           "Qp = y·ΣQb, y = 0,8/√(x−1) ; D = √(4Q/πv)", ["DTU 60.11 (méthode, valeurs à confirmer)"]),
    Engine("plumb.rainwater", "Débit eaux pluviales", "PLUMB", "1.0", RainIn, rainwater, "Q = C·i·A/3600"),
    Engine("hvac.cooling", "Bilan frigorifique simplifié", "HVAC", "1.0", CoolingIn, cooling,
           "Σ U·A·ΔT + Σ A·g·I + apports internes + 0,34·qv·ΔT + 0,83·qv·Δw"),
    Engine("air.duct", "Gaine circulaire et pertes de charge", "AIR", "1.0", DuctIn, duct,
           "D = √(4Q/πv) ; f Swamee-Jain ; Δp = f/D·ρv²/2·L + Σζ·ρv²/2"),
    Engine("air.renewal", "Renouvellement d'air", "AIR", "1.0", AirRenewalIn, air_renewal, "max(n·q/pers, V·taux)"),
    Engine("gc.column", "Pré-dimensionnement poteau BA", "GC", "1.0", ColumnIn, column,
           "Nu = 1,35G + 1,5Q ; Br ≥ Nu / [α(fc28/(0,9·1,5) + ρ·fe/1,15)]", ["CBA 93", "RPA 99 version 2003"]),
]}
