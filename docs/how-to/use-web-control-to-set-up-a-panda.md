# Use Web Control to set up a PandA

A {term}`Design` is the heart of your system implementation. It is an
interactive graphical representation of your system that helps you build and
manage:

- {term}`Block`s representing hardware components, logic gates, etc.
- The {term}`Link` connectivity between blocks, in terms of input
  ({term}`Sink Port`) and output ({term}`Source Port`) ports.
- The {term}`Attribute`s associated with blocks and links.
- The {term}`Method`s available to influence behaviour within blocks.

A Design is created in the Web Control **Layout** view.

## Add a block to a design

A block is added to a design by dragging it from the Block Palette into the
Layout view:

1. Select the **Palette** icon at the bottom of the Layout panel. The Block
   Palette opens, containing the set of blocks currently available to you.
2. Identify the block you wish to add. Hovering over it changes the mouse
   pointer from an arrow to a hand.
3. Press and hold the left mouse button to select the block, then drag it into
   the Layout panel.
4. Release the mouse button at the desired location.

The Block Palette icon is replaced by a full representation of the selected
block, showing:

- The block name (shown relative to its {term}`Parent Block`).
- An optional, configurable descriptive label (initially default text).
- {term}`Source Port`s that transmit output from the block, including their
  type.
- {term}`Sink Port`s that receive input to the block, including their type.

After adding a block, select it by hovering over it and clicking the left mouse
button. On selection, the {term}`Block Information Panel` listing every
attribute and method available to that block is shown in the right-hand panel.

:::{note}
On initially adding a new block to your design it is configured according to
its pre-defined default settings, retrieved from the underlying design
specification of that block.
:::

## Remove a block from a design

A block can be removed in one of two ways:

- **By dragging it to the Bin:**
  1. Select the block by hovering over it and clicking the left mouse button. A
     **Bin** icon appears at the bottom of the Layout panel.
  2. Holding down the left mouse button, drag the block over the **Bin** icon.
     The icon is highlighted.
  3. Release the left mouse button.
- **By pressing Delete or Backspace:**
  1. Select the block by hovering over it and clicking the left mouse button.
     The selected block is highlighted.
  2. Press the *Delete* or *Backspace* key.

:::{note}
Removing a block automatically removes all {term}`Source Port` and
{term}`Sink Port` links associated with it.
:::

## Work with the Block Palette

The Block Palette lists each block available to a design, based on the
constraints imposed by the underlying hardware.

When a block is selected from the palette for inclusion in a design it is
removed from the palette, so it cannot be included more than once. If all blocks
of a particular type have been added to a design, no more can be added because
the underlying hardware cannot represent them.

If a block is removed from a design it immediately becomes available again in
the Block Palette.

## Specify block attributes

The behaviour of a block is defined via its {term}`Attribute`s. Attributes are
pre-defined based on the function of the block and may carry default values as a
starting point for later customisation. A full list of the attributes for each
block is given in the documentation for that block.

### Types of attribute

Four types of attribute are available; a block may support zero or more
depending on its purpose:

| Type | Description |
|---|---|
| {term}`Input Attribute` | Identifies the source of data received into a block via a {term}`Sink Port` of the same name. |
| {term}`Output Attribute` | Identifies the value (or stream of values) transmitted out of a block via a {term}`Source Port` of the same name. |
| {term}`Parameter Attribute` | Can be set by a user while configuring a block, influencing the block's behaviour. |
| {term}`Readback Attribute` | Set automatically by a process in the execution environment. Cannot be set manually via the UI. |

Attributes whose value can be set at design time are denoted by a highlight
below the attribute value field.

### Obtain information about an attribute

Select the information icon next to an attribute in the
{term}`Block Information Panel` to open the Attribute Information Panel in the
right-hand panel. It displays:

- The fully qualified path to the attribute, uniquely identifying it within the
  design.
- Basic metadata: its type, a brief description, and whether it is writeable.
- The [attribute state](../explanations/understanding-attribute-state.md),
  including the severity of any issue and any corresponding message.
- Timestamp details showing when the attribute was last updated.

Attribute metadata and alarm-state information is derived from the underlying
block specification.

### Set a block attribute

Parameter, Input and Output attributes are set via the
{term}`Block Information Panel` of the block you wish to configure. The way an
attribute is set reflects its definition in the underlying block specification,
and this also hints at whether the attribute is editable. The UI provides four
input widgets — View/Edit button, Dropdown list, Text input, and Checkbox.

:::{admonition} 🚧 TODO — attribute input widgets (blocked: capture)
:class: warning

The four attribute input widgets (**View/Edit button**, **Dropdown list**,
**Text input** and **Checkbox**) need fresh screenshots before this subsection
can be written, and the source text for *Text input* is truncated mid-sentence
in the original. Tracked in [PandABlocks/meta-panda#13](https://github.com/PandABlocks/meta-panda/issues/13).

In brief, until then:

- **View/Edit button** — opens a {ref}`complex attribute <complex-attributes>`
  in the central panel; reads *Edit* if modifiable, *View* otherwise.
- **Dropdown list** — select a value from a list of pre-defined options valid
  for the attribute in its current block context.
- **Text input** — a free-text field accepting any alphanumeric string; press
  *Enter* to submit.
- **Checkbox** — switches the attribute's action on or off; an empty checkbox
  means *off*.
:::

:::{tip}
An attribute may hold a value that cannot be modified in the context of the
current design. Such attributes are shown greyed out.
:::

To configure an attribute:

1. Select the block by clicking it in the Layout panel. The block is highlighted
   and its {term}`Block Information Panel` opens on the right.
2. Find the attribute you wish to configure.
3. Edit the attribute value field as appropriate for the widget described above.

:::{note}
No data-type validation is performed on manually entered values in the UI.
Validation is performed by the backend server on receipt. If an invalid format
is detected, a [Warning](../explanations/understanding-attribute-state.md) icon
is shown.
:::

While a new value is being submitted, a
[Processing](../explanations/understanding-attribute-state.md) (spinning) icon
is displayed to the left of the modified attribute — see
[Attribute change lifecycle](#attribute-change-lifecycle). On success the icon
reverts to the information icon; on failure an
[Update Error](../explanations/understanding-attribute-state.md) icon is shown.

### Export attributes

The UI presents a hierarchical view of the system, with one or more
{term}`Parent Block`s encapsulating deeper levels of your design. By default,
at the top level you see only attributes of parent blocks — but an underlying
attribute in a {term}`Child Block` may influence its parent's behaviour. Every
parent block can therefore **Export** one or more attributes from its children
so they are displayed within the parent.

To specify an attribute for export:

1. Identify the attribute you wish to monitor outside the current layout level.
   Note its source, in the form `BlockName.Attribute`.
2. In the parent block, select the **View** option on the *Exports* attribute.
3. In the Export Table, select the first blank row (or add a new row).
4. In the **Source** column, use the dropdown to find the attribute to export.
5. In the **Export** column, enter the name to display when exported. Leave it
   blank to use the attribute's default name. User-specified display names must
   be in `camelCase`, e.g. *myAttribute*.

:::{note}
The `camelCase` convention is required so an appropriate attribute label can be
generated in the parent {term}`Block Information Panel`.
:::

Once exported, the attribute appears in the *Exported Attributes* section of the
parent's {term}`Block Information Panel`. Any number of attributes can be
exported from child blocks. Their order mirrors the order in which they were
added; to reorder, or to insert above/below an existing entry, use the
**Insert row above**, **Insert row below**, **Move Up** and **Move Down**
options in the Export Table.

To remove an exported attribute, open the parent's *Export* attribute,
select the information icon for the relevant row, and choose **Delete** on the
**Delete row** field.

To apply your changes, select **Submit** at the bottom of the Export Table, then
refresh the parent block to confirm the attributes have been promoted (or
removed). Select **Discard Changes** at any time to abandon edits without
affecting the recorded specification.

### Local vs. server attribute state

The physical hardware is configured from the design specification behind the
graphical representation. A change takes effect in hardware only when it is
submitted and recorded. It is therefore important to understand the difference
between *local* and *server* attribute state, particularly for
{term}`Parameter Attribute`s that can be modified directly in the UI.

- **Local** state is a parameter attribute that has been modified in the UI but
  not yet submitted. It has no effect on hardware. Locally modified attributes
  show the *edit* icon next to the attribute name. An attribute enters local
  state as soon as its value is changed and remains there until *Enter* is
  pressed to submit. If the server reports an error, the attribute stays in
  local state until the issue is resolved.
- **Server** state means the value has been recorded to the information server
  hosting the design specification. Server-state attributes are reflected in
  hardware and show the *information* icon.

:::{tip}
Do not confuse local/server attribute state with a *saved* design.
[Saving a design](save-restore-design.md) saves only attributes already in the
**server** state; locally modified fields are not saved. Equally, a
server-state attribute is not stored permanently until the overall design is
saved.
:::

(attribute-change-lifecycle)=
### Attribute change lifecycle

Recording a modified attribute value is referred to as a *put* action. Once the
put completes, the value takes immediate effect on any executing processes. If
an error is detected during the put it is abandoned and reported back to the UI.

The round trip from submission to use takes a small but non-deterministic time
while data is transferred, validated and recorded, so attribute modification is
not atomic. During this time the
[Processing](../explanations/understanding-attribute-state.md) (spinning) icon
replaces the information icon; its reversion is the only reliable indication
that the value has been recorded and is now in use.

```{figure} ../images/webcontrol/attribute_lifecycle.svg
:align: center

Attribute change lifecycle workflow
```

:::{tip}
Remember the three rules of attribute change:

- Changing an attribute value in the UI has no effect on the physical system
  until it has been *put*.
- Once the put completes, the change takes immediate effect.
- Changes are not stored permanently unless the design is
  [saved](save-restore-design.md); only *put* values are recorded in the saved
  design.
:::

(complex-attributes)=
## Complex attributes

An attribute may itself represent a collection of values that together define
the overall attribute. For example, the Sequencer block contains a single
attribute defining the sequence of steps performed by hardware when controlling
motor motion.

These values are presented as an Attribute Table, generated dynamically from the
attribute's specification within its block. For details of a specific table,
refer to the technical documentation of its block.

```{figure} ../images/webcontrol/attribute_table.png
:align: center

Example Attribute Table associated with a complex attribute
```

### Identify table attributes

A table attribute is identified by the **View/Edit** button associated with it.
Selecting the button opens the Attribute Table in the central panel.

### Specify attribute table content

On opening an Attribute Table you can define values, which (like attributes
themselves) may be selected from a list, enable/disable options, or text and
numerical inputs. After adding values, select **Submit** at the bottom of the
table to record them, or **Discard Changes** to abandon edits.

### Static vs. dynamic attribute tables

- **Static** tables have a fixed number of columns and rows; all fields must be
  completed to fully define the attribute.
- **Dynamic** tables have a fixed number of columns but a varying number of
  rows. At least one row must be present.

New rows are added in one of two ways:

- Select **Add** below the last row to append a new row.
- If row order matters (for example, a sequence of activities), select the edit
  icon on an existing row (or the information icon on a new row) and use
  **Insert row above**, **Insert row below**, **Move Up** or **Move Down**.

To remove a row, select the information icon on the row and choose **Delete** on
the **Delete row** field.

## Work with block methods

While {term}`Attribute`s define a block's *behaviour*, {term}`Method`s define
the *actions* it can perform. A method is represented as a button labelled with
the action it performs, executed only when the button is pressed.

There is currently a single method: *Save* on the {term}`Parent Block`, which
requires the name of the file to save the design to as its input parameter.
Method parameters:

- Can be edited directly in the {term}`Block Information Panel`.
- Exist in *local* state until the method's button is pressed.
- Are properties of their method rather than entities in their own right; they
  are never recorded on the server or saved in the persistent design.

### Obtain information about method execution

Selecting the information icon on a method displays two sources of information:

- The right-hand panel describes the method's purpose and required parameters.
- The central panel shows a log of each method execution in the current session,
  including submission and completion times, the completion status (e.g. success
  or failure), and any alarms. Selecting a parameter name in the table header
  opens information about that parameter in the right-hand panel.

## Block ports

Blocks may *receive* input via one or more {term}`Sink Port`s and *transmit*
output via one or more {term}`Source Port`s. A block's ports are listed in its
documentation. Ports are colour-coded by the type of information they carry:

| Port type | Key |
|---|---|
| Boolean | Blue |
| Int32 | Orange |

Information is transferred from a source port to a sink port via a
{term}`Link` — see [Linking blocks](#linking-blocks) below.

(linking-blocks)=
## Link blocks

Blocks are connected via {term}`Link`s. A link joins a {term}`Source Port` on
one block to a {term}`Sink Port` on another; both ports must be of the same
type. A block's ports and their specification are defined in its documentation.

### Create a block link

1. Hover over the {term}`Source Port` or {term}`Sink Port` at one terminus of
   the link. The port is temporarily highlighted.
2. Press and hold the left mouse button and drag the link to the port at the
   other terminus. The target port is temporarily highlighted.
3. Release the mouse button. If the link constraints below are respected, the
   link is displayed in the Layout.

```{figure} ../images/webcontrol/PANDA-new-link.png
:align: center

Creating a link between two blocks
```

:::{note}
If an error occurs during creation, details are displayed at the bottom of the
Layout panel.
:::

:::{tip}
To confirm a link was created correctly, click it. The link is highlighted and
the Link Information Panel opens, showing the {term}`Source Port` and
{term}`Sink Port` names.
:::

### Interrogate link attributes

A link has no attributes of its own, but selecting it shows information about its
{term}`Source Port` origin and {term}`Sink Port` target in the right-hand panel:

1. Hover over the link. It changes colour to denote it may be selected.
2. Click the left mouse button. The Link Information Panel opens on the right.

:::{caution}
You can modify the source and sink of a link from the Link Information Panel. Do
so cautiously — this changes how blocks are connected without any acknowledgement
that a change has occurred.
:::

### Remove a link

- **By pressing Delete or Backspace:** hover over the link, click to select it,
  then press *Delete* or *Backspace*.
- **Via the Link Information Panel:** select the link, then choose **Delete** in
  the Link Information Panel.

### Constraints when using links

- A {term}`Sink Port` can accept only a single link.
- Multiple links can originate from a {term}`Source Port`, connecting it to
  multiple blocks.
- Links can connect only a {term}`Source Port` and {term}`Sink Port` of the same
  logical type (e.g. boolean, int32). Port types are colour-coded in the Layout
  to aid identification.
