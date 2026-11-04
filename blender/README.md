# Арт профиля из Blender

`rose.py` рендерит шапку, разделители разделов, подвал и кадры анимации с розой
(Blender 5.2, EEVEE): белые розы из лепестков по золотому углу, серебристые завитки,
светящиеся перья и искры.

```bash
blender -b --factory-startup --python blender/rose.py -- hero assets/hero.png
blender -b --factory-startup --python blender/rose.py -- "div:Обо мне" assets/div_about.png
blender -b --factory-startup --python blender/rose.py -- footer assets/footer.png
blender -b --factory-startup --python blender/rose.py -- emblem frames 100 48
blender -b --factory-startup --python blender/rose.py -- avatar assets/avatar.png
blender -b --factory-startup --python blender/rose.py -- avatar:wreath assets/avatars/4-wreath.png  # single, monogram, wreath, light
blender -b --factory-startup --python blender/rose.py -- frame assets/avatars/avatar-frame.png  # transparent centre, put any picture under it
```

Кадры анимации собираются в GIF через Pillow.
