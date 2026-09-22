# Glossary

These are commonly used terms across the PandABlocks documentation.
Terms from the web control UI and from the FPGA/firmware layer are merged here
as the canonical reference; all other repos link to this page.

```{glossary}
App
: An `.ini` file that specifies the type and number of {term}`Block` instances
  to build together into an FPGA image (an `.ipk` package — or, pre-5.0, a
  legacy {term}`Zpkg` — loadable on a PandABlocks device).

Attribute
: A property of a {term}`Block`.  Attributes are divided into four categories:

  - {term}`Parameter Attribute`
  - {term}`Input Attribute`
  - {term}`Output Attribute`
  - {term}`Readback Attribute`

Attribute Group
: A logical grouping of related {term}`Attribute` instances within a
  {term}`Block`, presented as a collapsible section in the
  {term}`Block Information Panel`.

Block
: A piece of FPGA logic (or a software equivalent) that has a number of
  {term}`Field` instances and performs specified calculations on each FPGA clock
  tick.  In the web control UI a Block is the graphical manifestation of a
  component within a {term}`Design`, encapsulating its attributes, methods and
  connectivity to other blocks.

  Blocks may represent:

  - Input and output controllers (interfaces to the FPGA)
  - Configurable clocks
  - Logic lookup tables and logic gates
  - Soft blocks such as a SEQ, or hardware-connected blocks such as TTLIN

Block Information Panel
: Panel in the web control UI showing the {term}`Attribute` and {term}`Method`
  details of the currently selected {term}`Block`.

Child Block
: A {term}`Block` that appears within the {term}`Layout` of a
  {term}`Parent Block`.

Design
: The complete technical description of a system: the {term}`Block` instances
  it contains, their {term}`Attribute` values, and the {term}`Link` connections
  between them.  A Design is represented graphically as a {term}`Layout` in the
  web interface.

Design Element
: Any {term}`Block`, {term}`Attribute` or {term}`Link` currently in focus
  within the {term}`Layout` view.

Field
: An input, output or parameter of a {term}`Block`.

Flowgraph
: Synonym for {term}`Layout` — the graphical representation of a {term}`Design`
  showing all {term}`Design Element` connections.

FMC
: [FPGA Mezzanine Card](https://en.wikipedia.org/wiki/FPGA_Mezzanine_Card) —
  a standard expansion connector for FPGA carrier boards.  Several PandABlocks
  FPGA bitstreams target specific FMC cards.

Input Attribute
: An attribute that identifies the value (or stream of values) received into a
  {term}`Block` via a {term}`Sink Port`.  There is a 1:1 mapping between an
  Input Attribute and a Sink Port.

Input Port
: Synonym for {term}`Sink Port`.

Layout
: The graphical representation of a {term}`Design` in the web control, showing
  {term}`Block` instances and the {term}`Link` connections between them.

Link
: A connection that transfers data from a {term}`Source Port` on one
  {term}`Block` to a {term}`Sink Port` on another.  Links can only be made
  between ports of the same logical type (e.g. bit→bit, position→position).

Method
: An **action** that can be performed by a {term}`Block`, such as ARM or
  DISARM.

Module
: A directory in PandABlocks-FPGA containing {term}`Block` definitions,
  logic, simulations and timing files.  A module typically contains a single
  soft Block definition or a set of hardware Blocks for a particular
  {term}`Target Platform`, {term}`SFP` or {term}`FMC` card.

Output Attribute
: An attribute that identifies the value (or stream of values) transmitted via a
  {term}`Source Port` out of a {term}`Block`.  There is a 1:1 mapping between
  an Output Attribute and a Source Port.

Output Port
: Synonym for {term}`Source Port`.

PandABlocks Device
: A Zynq 7030 (or compatible) based device loaded with the PandABlocks firmware,
  running the PandABlocks server framework.

PandABox
: A {term}`PandABlocks Device` manufactured jointly by
  [Diamond Light Source](https://www.diamond.ac.uk) and
  [SOLEIL](https://www.synchrotron-soleil.fr).
  Schematics are on [Open Hardware](https://www.ohwr.org/projects/pandabox/wiki).

Parameter Attribute
: An attribute whose value can be set by a user to influence the behaviour of
  a {term}`Block`.

Parent Block
: A {term}`Block` that aggregates one or more {term}`Child Block` instances
  each performing an activity in support of the parent's functionality.

Readback Attribute
: An attribute whose value is set automatically by the execution environment.
  Readback attributes cannot be set manually via the UI.

Root Block
: The outermost entity displayed in the web control UI.  Selecting the top-level
  {term}`Design` block shows the whole system; navigating into a child presents
  that child as the root.

SFP
: [Small Form-factor Pluggable transceiver](https://en.wikipedia.org/wiki/Small_form-factor_pluggable_transceiver) —
  a standard optical/electrical interface used on some PandABlocks hardware.

Sink Port
: A port on a {term}`Block` that accepts incoming data.  Every Sink Port has a
  pre-defined type declared in the Block specification.

Source Port
: A port on a {term}`Block` that transmits data generated within that Block.
  Every Source Port has a pre-defined type declared in the Block specification.

Target Platform
: The physical Zynq-based hardware loaded with PandABlocks firmware, such as a
  {term}`PandABox` or a Picozed Carrier.

Zpkg
: A specially formatted tar file of built files that can be deployed to a
  PandABlocks device (legacy pre-5.0 format; replaced by opkg `.ipk` packages
  from release 5.0 onwards).
```
