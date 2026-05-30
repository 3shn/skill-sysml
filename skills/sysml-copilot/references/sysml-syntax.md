# SysML v2 textual syntax — working reference

A focused guide to writing valid textual SysML v2 (`.sysml`). It covers the constructs the
co-pilot emits most often and the rules the compiler actually enforces. For the complete grammar
see `SysML-textual-bnf.kebnf` (vendored alongside this file); for worked, validated models see
`examples/`. The validator (`validate_sysml_file`) is the final authority — this reference helps
you write code that passes it on the first try.

## The one idea that explains most errors: definitions vs. usages

SysML v2 separates **definitions** (`part def`, `port def`, `attribute def`, `item def`,
`action def`, `state def`, `connection def`, `interface def`, `requirement def`, `constraint def`,
`calc def`, `enum def`) from **usages** (`part`, `port`, `attribute`, `item`, `action`, …).

- A definition is a reusable type: `part def Engine { … }`.
- A usage is an occurrence of a definition in a context: `part eng : Engine;`.
- **A usage must be typed by a *definition*, never by another usage.** Typing `part eng : engOther`
  (where `engOther` is a usage) triggers *"A usage must be typed by definitions."* Likewise a
  `port` must be typed by a `port def`, an `item` by an `item def`, etc.

## File and package structure

```sysml
package 'My Package' {            // names with spaces/symbols use single quotes
    private import ScalarValues::*;   // bring in library names; private = not re-exported
    public  import ISQ::*;            // public = re-exported to importers
    // … definitions and usages …
}
```

Names: a plain identifier (`Vehicle`, `fuelPort`) or a quoted name (`'Fuel Out Port'`).
A short-name/alias may precede the name in angle brackets: `requirement def <'1'> MassReq { … }`.

## Specialization operators (get these right — most semantic errors come from here)

| Operator / keyword | Meaning | Example |
| --- | --- | --- |
| `:` | type a usage by a definition | `attribute mass : MassValue;` |
| `:>` | specialize (defs) / subset (usages) | `part def Car :> Vehicle;`  `attribute mass :> ISQ::mass;` |
| `:>>` or `redefines` | redefine an inherited feature | `attribute :>> massActual = …;`  `part redefines eng { … }` |
| `specializes` | KerML form of `:>` (in `.kerml` libs) | `datatype Real specializes Complex;` |
| `~` | conjugate a port | `port enginePort : ~FuelOutPort;` |

## Parts and attributes

```sysml
part def Vehicle {
    attribute mass : Real;              // typed by a datatype
    attribute status : VehicleStatus;   // typed by an attribute def
    part eng : Engine;                  // composite part usage
    ref part driver : Person;           // referential (non-composite) part
}
attribute def VehicleStatus { attribute gear : Integer; }
part def Engine;                        // empty body is fine
```

Redefinition in usages:

```sysml
part smallVehicle : Vehicle {
    part redefines eng { part redefines cyl[4]; }   // multiplicities in [ ]
}
```

## Quantities and units — always ground these in the library

Engineering attributes should reference standard quantities from the `ISQ` library and units from
`SI`. **Do not invent quantity or unit names** — look them up with `query_library` first, then use
the real qualified name.

```sysml
private import ISQ::*;
private import SI::*;

part def Tank {
    attribute capacity : VolumeValue;      // ISQ value type
    attribute mass : MassValue;
}
// literal with a unit uses [ ]:
constraint { fuelMass > 0[kg] }            // SI::kg
attribute dryMass : MassValue = 1200[kg];
```

Common lookups: `mass`→`ISQBase::mass`/`ISQBase::MassValue`, `kilogram`→`SI::kilogram` (alias `SI::kg`),
`newton`→`SI::newton`, `Real`/`Integer`/`Boolean`/`String`→`ScalarValues::*`.

## Ports and items (flows)

```sysml
port def FuelOutPort {
    attribute temperature : Temp;
    out item fuelSupply : Fuel;     // direction: in / out / inout
    in  item fuelReturn : Fuel;
}
part def Engine { port engineFuelPort : ~FuelOutPort; }   // conjugate for the matching side
```

## Connections and interfaces

```sysml
connection def Mounting { end part bracket : Bracket; end part frame : Frame; }
part def Assembly {
    part b : Bracket; part f : Frame;
    connect b to f;                         // simple connector
    interface engineFuel : FuelInterface connect engine.fuelPort to tank.outPort;
}
```

## Actions and states (behavior)

```sysml
action def Provide { in item fuel : Fuel; out item torque : Torque; }
action def OperateVehicle {
    first start;
    then action generate : Provide;
    then done;
}
state def VehicleStates { entry; state off; transition off then on; state on; }
```

## Requirements (a core co-pilot deliverable)

```sysml
requirement def MassLimitationRequirement {
    doc /* The actual mass shall be ≤ the required mass. */
    attribute massActual : MassValue;
    attribute massReqd : MassValue;
    require constraint { massActual <= massReqd }
}
requirement def <'1'> VehicleMassReq :> MassLimitationRequirement {
    subject vehicle : Vehicle;                       // the thing the requirement is about
    attribute redefines massActual = vehicle.dryMass + vehicle.fuelMass;
    assume constraint { vehicle.fuelMass > 0[kg] }
}
// satisfy a requirement with a design element:
satisfy VehicleMassReq by myVehicle;
```

Note: when a requirement has a `subject`, declare it as shown; the compiler enforces
*"Subject must be first parameter."* Use `require constraint { … }` for required conditions and
`assume constraint { … }` for assumptions.

## Comments and documentation

```sysml
// line comment
/* block comment */
doc /* attached documentation, allowed inside any definition */
comment about Vehicle /* a comment targeting an element */
```

## Pitfalls the validator will flag (and how to avoid them)

- *"A usage must be typed by definitions"* / *"A port must be typed by port definitions"* — type
  usages with `def` types, not other usages.
- *"Couldn't resolve reference to …"* — the name isn't in scope. Add the right `import`, fix the
  qualified name, or (for cross-file models) pass the sibling files via `context_paths` when
  validating. For library names, confirm the exact qualified name with `query_library`.
- *"Subject must be first parameter"* — declare `subject` correctly inside requirements.
- *"Must reference an occurrence"* — `event`/occurrence usages must reference an occurrence feature.
- Multiplicities use square brackets (`[4]`, `[4..6]`, `[*]`); unit literals use `value[unit]`.
