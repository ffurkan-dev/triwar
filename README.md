# Triwar

Kayıtlı kullanıcıların birbirleriyle 1v1 trivia mücadeleleri yaptığı web uygulaması (Django + Supabase Postgres + Vercel). Ayrıntılar: [docs/TRIWAR_PLAN.md](docs/TRIWAR_PLAN.md).

## Lokal kurulum

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # değerleri doldur
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

`DATABASE_URL` tanımlı değilse yerel `db.sqlite3` kullanılır (RLS migration'ı yalnızca Postgres'te çalışır).

## Testler

```bash
DATABASE_URL= python manage.py test
```

`DATABASE_URL=` boş verilir ki testler Supabase yerine yerel SQLite'ta çalışsın.

## Harita verisi

`static/maps/world.svg` ve `game/fixtures/countries.json` Natural Earth 110m verisinden üretilir (repoda hazır gelir). Yeniden üretmek için:

```bash
python scripts/build_world_svg.py   # GeoJSON'u geçici olarak indirir
python manage.py loaddata countries
```

## Supabase

1. Supabase'de bir proje oluştur; Project Settings → Database'den bağlantı dizelerini al.
2. `.env` içine yaz:
   - `DATABASE_URL`: Transaction Pooler (port 6543) — uygulama bunu kullanır.
   - `MIGRATION_DATABASE_URL`: Session Pooler / direkt bağlantı (port 5432) — yalnızca migration için.
3. Migration'ı Supabase'e uygula (Vercel build'inde çalışmaz):
   ```bash
   USE_MIGRATION_DB=1 python manage.py migrate
   USE_MIGRATION_DB=1 python manage.py loaddata countries
   ```
4. Supabase → Advisors panelinde RLS uyarısı kalmadığını kontrol et. Yeni tablo eklenince RLS migration'ı (`game/migrations/0001_enable_rls.py`) örnek alınarak tekrarlanır.

## Vercel

1. GitHub reposunu Vercel'de içe aktar (Django otomatik algılanır; `vercel.json` build'de `collectstatic` çalıştırır).
2. Environment Variables: `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`.
