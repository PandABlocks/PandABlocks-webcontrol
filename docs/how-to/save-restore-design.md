# Save and restore a design

A {term}`Design` can be saved to a {term}`Parent Block` and reopened later. This
page covers saving the current design and opening an existing one. To build or
edit a design, see
[](use-web-control-to-set-up-a-panda.md).

:::{tip}
Saving a design saves only attributes already in the **server** state — locally
modified fields are not saved. See
[Local vs. server attribute state](use-web-control-to-set-up-a-panda.md#local-vs-server-attribute-state).
:::

## Save a design

You can save your design at any time during creation or modification, and we
recommend you do so regularly.

1. Navigate to the {term}`Root Block` representing the highest level of the
   design you wish to save.
2. Navigate to the *Save* attribute group at the bottom of the left-hand panel.
   Expand it if necessary.
3. Enter a descriptive name for the design in the *Design Name* field. This
   name is used later to identify the design.

   :::{tip}
   To save the design with the same name as the currently open design, leave the
   *Design Name* field blank.
   :::

4. Select the **Save** button. The information icon to the left of the button
   spins while the save is in progress, returning to the information icon when
   the design is saved.

:::{note}
If an error is detected during the save, a red warning icon is displayed next to
the button.
:::

## Open an existing design

A {term}`Parent Block` may hold multiple {term}`Design`s, each reflecting
operation of that block in a different scenario. Only one design can be in use at
any given time; by default this is the design open at the time of system
execution.

When a parent block is opened, a list of all its designs is available via the
*Design* attribute in the left-hand panel. Selecting an existing design presents
it in the central Layout panel.

To open an existing design:

1. Navigate to the {term}`Parent Block` representing the highest level of the
   system you wish to use.
2. Navigate to the *Design* attribute and select the dropdown arrow to display
   the list of available designs.
3. Select the design you wish to use.
4. Select the **View/Edit** button on the *Layout* attribute.

:::{tip}
If no previously saved designs exist, the *Design* attribute list is empty.
:::
