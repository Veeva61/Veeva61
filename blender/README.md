# Арт профиля из Blender

`make.py` рендерит шапку, заголовки разделов и кадры анимации «VIBE CODER» (Blender 5.2, EEVEE).

```bash
set VT=std
blender -b --factory-startup --python blender/make.py -- hero assets/hero.png
blender -b --factory-startup --python blender/make.py -- about assets/sec_about.png
blender -b --factory-startup --python blender/make.py -- gif frames 100 40
```

Разделы: `about`, `vibe`, `stack`, `projects`, `stats`, `snake`, `thanks`.
Кадры анимации собираются в GIF через Pillow.
