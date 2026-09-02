from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')
marker = '</style>'
override = '''

/* Telegram card sizing + arrow spacing */
.telegram-card-stage{
  width:min(1050px,92%)!important;
  grid-template-columns:minmax(220px,.55fr) minmax(0,1.45fr)!important;
  gap:clamp(56px,6vw,92px)!important;
  margin:2px auto 64px!important;
  padding:14px 32px 24px!important;
}
.telegram-card-link{
  width:min(100%,650px)!important;
}
.telegram-card-arrow{
  left:calc(100% + 18px)!important;
  top:66%!important;
  width:108px!important;
}
@media(max-width:900px){
  .telegram-card-stage{
    width:min(700px,94%)!important;
    gap:24px!important;
    padding:10px 12px 20px!important;
    margin:0 auto 52px!important;
  }
  .telegram-card-link{width:88%!important}
  .telegram-card-arrow{
    left:calc(100% + 12px)!important;
    top:64%!important;
    width:88px!important;
  }
}
@media(max-width:620px){
  .telegram-card-link{width:92%!important}
  .telegram-card-arrow{
    left:calc(100% + 8px)!important;
    top:62%!important;
    width:76px!important;
  }
}
'''
if '/* Telegram card sizing + arrow spacing */' not in s:
    if marker not in s:
        raise SystemExit('style closing tag not found')
    s = s.replace(marker, override + '\n' + marker, 1)
p.write_text(s, encoding='utf-8')
