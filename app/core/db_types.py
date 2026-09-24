from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """DateTime toujours UTC de bout en bout, y compris sur SQLite (qui ne préserve pas le
    fuseau d'une valeur "timezone-aware" au round-trip malgré `DateTime(timezone=True)` — elle
    revient naïve, et l'API la sérialisait alors sans offset, ex. "2026-08-26T13:30:00" au lieu
    de "...+00:00"). Un client dans un fuseau non-UTC (`Africa/Tunis` sur le téléphone de test)
    réinterprète alors ces chaînes ambiguës comme de l'heure locale : décalage d'affichage égal à
    l'offset local. Voir SUIVI_PROJET.md pour l'incident complet.

    Stocke toujours en base une valeur naïve mais garantie UTC ; ré-attache systématiquement
    `tzinfo=UTC` à la lecture, donc l'API renvoie toujours une datetime avec offset explicite.
    Tout le code applicatif écrit déjà exclusivement des datetimes UTC-aware
    (`datetime.now(timezone.utc)`, ou des dates parsées par Pydantic depuis un ISO avec offset) —
    voir `_require_utc` ci-dessous, qui échoue fort plutôt que de stocker silencieusement une
    valeur ambiguë si ce n'était plus le cas.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                f"UTCDateTime a reçu une datetime naïve ({value!r}) — toujours utiliser "
                "datetime.now(timezone.utc) ou une datetime déjà timezone-aware."
            )
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
