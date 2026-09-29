# Understanding attribute state

At any given time an attribute can be in one of eight states.  State depends on:

- The current value of the attribute.
- The pre-defined permissible operating range or threshold for that attribute.
- The workflow the attribute is currently involved in.
- The overall context of the control system.

State is shown as an icon to the left of the attribute name in the
{term}`Block Information Panel`.

## State reference

### Normal

Data is within an acceptable operating threshold or range.  For a
{term}`Parameter Attribute` this also means the value has been successfully
committed to the server.

```{figure} ../images/attribute-state/normal.svg
:align: center
:width: 32px

Normal state icon
```

### Processing

Data has been submitted to the server or a retrieval request has been made.
A response is being awaited.

```{figure} ../images/attribute-state/processing.svg
:align: center
:width: 32px

Processing state icon
```

### Locally Edited

The value has been changed in the UI but not yet committed to the server.
The local edit has no effect on the running system and will not be saved as
part of the {term}`Design` until it is submitted.

```{figure} ../images/attribute-state/locally-edited.svg
:align: center
:width: 32px

Locally Edited state icon
```

### Update Error

The value submitted to the server was not accepted — typically because it
failed the validation defined in the Block specification.

```{figure} ../images/attribute-state/update-error.svg
:align: center
:width: 32px

Update Error state icon
```

### Warning

An issue has been detected that requires investigation.  Data is outside
normal operating parameters but is still considered acceptable.

```{figure} ../images/attribute-state/warning.svg
:align: center
:width: 32px

Warning state icon
```

### Error

An issue has been detected and an error has been reported by the server.
Data is outside acceptable operating conditions; immediate action is
recommended.

```{figure} ../images/attribute-state/error.svg
:align: center
:width: 32px

Error state icon
```

### Invalid

The overall block context has changed since the UI was last accessed.
Displayed data may no longer be accurate or consistent with the current
{term}`Design`.

```{figure} ../images/attribute-state/invalid.svg
:align: center
:width: 32px

Invalid state icon
```

### Disconnected

Communication with the block hosting the attribute has been lost by the
server.  Immediate investigation is recommended.

```{figure} ../images/attribute-state/disconnected.svg
:align: center
:width: 32px

Disconnected state icon
```

## Presenting status information

Within Block Information Panels, the state icon appears to the left of each
attribute name.

When viewing historical data in the
[attribute value table](../how-to/monitor-attribute-values#working-with-numerical-tables),
the corresponding icon is shown against each row.

When viewing historical data in the
[attribute chart](../how-to/monitor-attribute-values#working-with-charts),
the line colour reflects the alarm state.

:::{note}
Operating ranges and threshold values are not defined in the UI — they are
configured in the underlying Block specification and reflected into the UI.
Refer to the specific block documentation for details.
:::
