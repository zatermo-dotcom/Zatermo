"""Moteurs de pré-dimensionnement déterministes.

Principes :
  * formules explicites, paramètres visibles, version du moteur enregistrée avec chaque calcul ;
  * aucune donnée réglementaire ou climatique « inventée » : les valeurs dépendant du site ou d'un texte
    applicable sont des entrées obligatoires ou des paramètres par défaut signalés comme « à confirmer » ;
  * chaque résultat porte un avertissement : pré-dimensionnement à vérifier et signer par un ingénieur habilité.
"""
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

DISCLAIMER = ("Pré-dimensionnement indicatif produit par un moteur déterministe. Il ne remplace ni une note de calcul "
              "complète ni la vérification et la signature d'un ingénieur habilité, conformément aux textes applicables.")


@dataclass
class Engine:
    code: str
    name: str
    discipline: str
    version: str
    input_model: type[BaseModel]
    run: Callable[[Any], dict]
    method: str
    references: list[str] = field(default_factory=list)


def result(outputs: dict, warnings: list[str] | None = None) -> dict:
    return {"outputs": outputs, "warnings": (warnings or []) + [DISCLAIMER]}
