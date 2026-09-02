from pathlib import Path

p = Path("index.html")
s = p.read_text(encoding="utf-8")

old_css = """.private{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px}
.pc{min-height:205px;border:1px solid var(--line);border-radius:23px;padding:24px;position:relative;overflow:hidden;background:var(--paper)}
.pc:first-child{background:#171815;color:white}
.pc:nth-child(2){background:linear-gradient(135deg,var(--accent-soft),#f7f4e8)}
.pc small{text-transform:uppercase;letter-spacing:.1em;opacity:.65;font-size:9px}
.pc h3{font-size:34px;line-height:.95;letter-spacing:-.055em;margin:52px 0 8px}
.pc p{font-size:11px;opacity:.7}
.pc b{position:absolute;right:20px;bottom:20px;width:43px;height:43px;border-radius:50%;background:var(--lime);color:#111;display:grid;place-items:center}
"""

new_css = """.private{display:grid;grid-template-columns:1fr;gap:18px;margin-top:18px}
.pc{
  min-height:300px;
  border:1px solid var(--line);
  border-radius:28px;
  padding:34px 32px;
  position:relative;
  overflow:hidden;
  display:block;
  background:var(--paper);
  transition:transform .28s ease,box-shadow .28s ease;
  isolation:isolate;
}
.pc:hover{transform:translateY(-2px)}
.pc__content{position:relative;z-index:4;max-width:58%}
.pc small{text-transform:uppercase;letter-spacing:.12em;opacity:.68;font-size:10px;display:block;margin-bottom:52px}
.pc h3{font-size:clamp(38px,4.3vw,66px);line-height:.9;letter-spacing:-.06em;margin:0 0 14px;font-weight:500}
.pc p{font-size:13px;line-height:1.45;opacity:.74;margin:0;max-width:620px}
.pc b{position:absolute;right:24px;bottom:24px;width:54px;height:54px;border-radius:50%;background:var(--lime);color:#111;display:grid;place-items:center;z-index:6;font-size:20px}

.pc--caseplace{background:#171815;color:#fff}
.pc--caseplace .pc__logo{
  position:absolute;
  right:9%;
  top:50%;
  width:min(38%,520px);
  height:auto;
  transform:translateY(-50%);
  filter:brightness(0) invert(1);
  opacity:.96;
  z-index:2;
  pointer-events:none;
}

.pc--smeshariki{background:linear-gradient(135deg,#f7d8c8 0%,#f7eee4 62%,#f8f3ea 100%);color:var(--ink)}
.pc--smeshariki .pc__content{max-width:54%}
.pc--smeshariki .pc__art{
  position:absolute;
  right:4%;
  bottom:-150px;
  width:min(36%,410px);
  height:auto;
  z-index:2;
  pointer-events:none;
  transform:translate3d(0,0,0) rotate(0deg);
  transform-origin:58% 86%;
  transition:transform .46s cubic-bezier(.18,.82,.2,1);
  filter:drop-shadow(0 14px 18px rgba(17,18,15,.10));
}
.pc--smeshariki:hover .pc__art{transform:translate3d(0,-42px,0) rotate(-7deg)}

@media(max-width:900px){
  .pc{min-height:250px;padding:28px 24px}
  .pc small{margin-bottom:34px}
  .pc__content{max-width:62%}
  .pc--caseplace .pc__logo{right:8%;width:34%}
  .pc--smeshariki .pc__art{right:2%;bottom:-118px;width:38%}
  .pc--smeshariki:hover .pc__art{transform:translate3d(0,-28px,0) rotate(-6deg)}
}
@media(max-width:620px){
  .private{gap:14px}
  .pc{min-height:245px;padding:24px 20px 72px}
  .pc small{margin-bottom:26px;font-size:9px}
  .pc h3{font-size:36px}
  .pc p{font-size:12px}
  .pc__content,.pc--smeshariki .pc__content{max-width:100%}
  .pc--caseplace .pc__logo{right:72px;top:auto;bottom:24px;transform:none;width:40%;opacity:.26}
  .pc--smeshariki .pc__art{right:-2%;bottom:-78px;width:44%;opacity:.92}
  .pc--smeshariki:hover .pc__art{transform:translate3d(0,-18px,0) rotate(-5deg)}
  .pc b{right:16px;bottom:16px;width:48px;height:48px}
}
"""

old_html = """    <div class=\"private\">
      <a class=\"pc\" href=\"https://drive.google.com/file/d/1apCqN8SaCv9i9adfkectLfnmaVJxQ5ZJ/view?usp=drive_link\" target=\"_blank\">
        <small>Private portfolio · 01</small><h3>Commercial<br>Work</h3><p>Additional professional projects and production work.</p><b>↗</b>
      </a>
      <a class=\"pc\" href=\"https://drive.google.com/file/d/1fb7VxaNmrspl9Uh4E_ezld3GIZg0aYt0/view?usp=drive_link\" target=\"_blank\">
        <small>Private portfolio · 02</small><h3>More<br>Projects</h3><p>Extra commercial materials that are not published publicly.</p><b>↗</b>
      </a>
    </div>"""

new_html = """    <div class=\"private\">
      <a class=\"pc pc--caseplace\" href=\"https://drive.google.com/file/d/1apCqN8SaCv9i9adfkectLfnmaVJxQ5ZJ/view?usp=drive_link\" target=\"_blank\" rel=\"noreferrer\">
        <div class=\"pc__content\">
          <small>Частный портфель · 01</small>
          <h3>Case Place</h3>
          <p>Коммерческие работы и успехи с моего прошлого места работы (метрики, e-comm, реклама - все сюда!)</p>
        </div>
        <img class=\"pc__logo\" src=\"caseplace-logo.png\" alt=\"Case Place logo\">
        <b>↗</b>
      </a>

      <a class=\"pc pc--smeshariki\" href=\"https://drive.google.com/file/d/1fb7VxaNmrspl9Uh4E_ezld3GIZg0aYt0/view?usp=drive_link\" target=\"_blank\" rel=\"noreferrer\">
        <div class=\"pc__content\">
          <small>Частный портфель · 02</small>
          <h3>СМЕШАРИКИ × Case Place</h3>
          <p>Лицензионный проект, проведенный под моим чутким контролем и выполненный моими золотыми руками</p>
        </div>
        <img class=\"pc__art\" src=\"smeshariki.png\" alt=\"Смешарики illustration\">
        <b>↗</b>
      </a>
    </div>"""

if old_css not in s:
    raise SystemExit("Old private portfolio CSS block not found")
if old_html not in s:
    raise SystemExit("Old private portfolio HTML block not found")

s = s.replace(old_css, new_css, 1)
s = s.replace(old_html, new_html, 1)
p.write_text(s, encoding="utf-8")
print("Private portfolio cards patched")
