# Motion Guidelines

Motion is polish, not decoration.

Allowed:

- page fade or slide, 150-220ms;
- card entrance, 150-200ms;
- tab content fade;
- dialog scale from 0.98 to 1;
- empty state fade.

Avoid:

- pulsing errors;
- infinite status animation;
- dense table animation;
- log animation;
- aggressive critical-risk transforms;
- layout shift.

The app uses reduced-motion-aware primitives where motion is applied.
