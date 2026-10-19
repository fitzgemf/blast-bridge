"""FICTIONAL demo roster. These people do not exist; names and units are invented."""

from .models import CrewPosition, Person

_UNIT = "Demo Rocket Battery (FICTIONAL)"

_ROSTER = (
    ("Avery Kestrel", "KESTREL", "1st Section", CrewPosition.CHIEF),
    ("Jordan Pike", "PIKE", "1st Section", CrewPosition.GUNNER),
    ("Riley Marsh", "MARSH", "1st Section", CrewPosition.DRIVER),
    ("Sam Okafor-Lind", "LINDY", "1st Section", CrewPosition.GUNNER),
    ("Casey Thorne", "THORNE", "2nd Section", CrewPosition.CHIEF),
    ("Morgan Vale", "VALE", "2nd Section", CrewPosition.GUNNER),
    ("Taylor Brook", "BROOK", "2nd Section", CrewPosition.DRIVER),
    ("Devon Ashby", "ASHBY", "2nd Section", CrewPosition.DRIVER),
    ("Quinn Halloway", "HALO", "3rd Section", CrewPosition.CHIEF),
    ("Reese Calder", "CALDER", "3rd Section", CrewPosition.GUNNER),
    ("Emerson Tull", "TULL", "3rd Section", CrewPosition.DRIVER),
    ("Harper Yoon", "YOON", "3rd Section", CrewPosition.GUNNER),
)

DEMO_PEOPLE = tuple(
    Person(
        person_id=f"FIC-{i:03d}",
        display_name=name,
        callsign=callsign,
        unit=_UNIT,
        section=section,
        home_position=position,
    )
    for i, (name, callsign, section, position) in enumerate(_ROSTER, start=1)
)
