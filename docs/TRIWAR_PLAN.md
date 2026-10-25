# Triwar — Proje Planı ve Claude Code Rehberi

> Bu dosya Triwar projesinin tek kaynak dokümanıdır. Claude Code her fazda önce bu dosyayı okumalı, yalnızca istenen fazı uygulamalı ve faz bitince "Faz Durumu" tablosunu güncellemelidir.

---

## 1. Proje Özeti

**Triwar**, kayıtlı kullanıcıların birbirleriyle **1v1 trivia mücadeleleri** yaptığı bir web uygulamasıdır.

- Kullanıcı bir **oda kurar**, oda kurarken **mücadele türünü** ve **süre sınırını** seçer.
- Lobide açık odalar listelenir: odayı kuranın **kullanıcı adı**, **mücadele türü** ve **süre sınırı** görünür.
- Başka bir kullanıcı odaya katılınca maç başlar.
- İlk (ve şimdilik tek) mücadele türü: **Ülke Bulmaca** — dilsiz dünya haritasında bir ülke boyanır, oyuncular hangi ülke olduğunu bulmaya çalışır.
- Süre sınırı seçenekleri: **20 saniye** veya **45 saniye** (soru başına).

**Amaç:** Çalışan, sade bir **prototip**. Karmaşık teknolojilerden kaçınılır; özellikler fazlar halinde eklenir.

---

## 2. Teknoloji Yığını ve Kısıtlar

| Katman | Seçim | Not |
|---|---|---|
| Backend | Python 3.12 + Django 5.x | Django'nun yerleşik auth, ORM, template ve admin'i kullanılır |
| Veritabanı | Supabase (PostgreSQL) | Yalnızca Postgres olarak kullanılır; Supabase Auth/Realtime **şimdilik kullanılmaz** |
| Deployment | Vercel (Python runtime) | Serverless — kalıcı süreç, WebSocket, arka plan işçisi **yok** |
| Frontend | Saf HTML + CSS + JavaScript | Framework yok (React/Vue/Tailwind yok). Django template'leri + `fetch` |
| Statik dosyalar | WhiteNoise | |

### Mimari kararlar (önemli)

1. **Gerçek zamanlılık = polling.** Vercel serverless olduğu için WebSocket / Django Channels kullanılamaz. Maç ve lobi durumu, frontend'in belirli aralıklarla JSON endpoint'lerini sorgulamasıyla güncellenir (lobi: 3 sn, bekleme odası: 2 sn, maç: 1 sn). İleride Supabase Realtime'a geçilebilir.
2. **Sunucu otoriterdir.** Süre, doğru cevap ve puan sunucuda belirlenir. Client'taki geri sayım yalnızca görseldir. Doğru cevap, tur süresi bitmeden veya iki oyuncu da cevaplamadan client'a **gönderilmez**.
3. **Tembel (lazy) durum ilerletme.** Arka plan işçisi olmadığından, tur bitişi / sonraki tura geçiş / maç bitişi, gelen her istekte (state polling veya cevap gönderme) zaman damgalarına bakılarak hesaplanır. Bu işlem `transaction.atomic()` + `select_for_update()` ile yapılır ki iki istek aynı anda ilerletmesin.
4. **Genişletilebilir mücadele türleri.** Her mücadele türü ayrı bir Python modülüdür ve ortak bir arayüzü uygular (bkz. Bölüm 6). Yeni tür eklemek = yeni modül + kayıt.
5. **Yeni bağımlılık eklemeden önce sor.** `requirements.txt` minimum tutulur.

### Bağımlılıklar (başlangıç)

```
Django>=5.0,<6.0
psycopg[binary]
dj-database-url
whitenoise
python-dotenv
```

---

## 3. Supabase + Django Bağlantı Notları

- Django, Supabase'e `DATABASE_URL` ile bağlanır. Serverless ortam için **Transaction Pooler** bağlantı dizesi (port `6543`) kullanılır.
- Transaction pooler (PgBouncer/Supavisor transaction mode) ile uyum için:
  - `CONN_MAX_AGE = 0`
  - `DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True`
- **Migration'lar Vercel build'inde çalıştırılmaz.** Lokal makineden `python manage.py migrate` ile Supabase'e uygulanır (gerekirse migration için Session Pooler / direkt bağlantı, port `5432`, ayrı bir env değişkeniyle).
- **Güvenlik — RLS:** Supabase, `public` şemasındaki tabloları otomatik REST API (PostgREST) ile dışarı açar. Django tabloları (özellikle `auth`/kullanıcı tablosu, şifre hash'leri) bu yolla okunabilir hale gelmesin diye **tüm tablolarda RLS etkinleştirilir, policy eklenmez.** Django `postgres` rolüyle bağlandığı için etkilenmez. Bunu yapan bir migration (`RunSQL`) eklenir ve her yeni tablo için tekrarlanır. Supabase "Advisors" panelinde uyarı kalmamalıdır.
- Supabase `anon` / `service_role` anahtarları frontend'e **asla** konmaz (şimdilik hiç gerekmiyor).

### Ortam değişkenleri (`.env.example`)

```
SECRET_KEY=
DEBUG=True
DATABASE_URL=postgresql://postgres.xxxx:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres
MIGRATION_DATABASE_URL=postgresql://postgres.xxxx:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
ALLOWED_HOSTS=localhost,127.0.0.1,.vercel.app
CSRF_TRUSTED_ORIGINS=https://*.vercel.app
```

`.env` dosyası `.gitignore`'da olmalıdır.

---

## 4. Vercel Notları

- Vercel'in **güncel** Django/Python dokümantasyonu kontrol edilerek yapılandırma kurulur (Vercel MCP bağlıysa `search_vercel_documentation` kullanılabilir). Tahminle `vercel.json` yazma; dokümana göre yaz.
- WSGI giriş noktası Vercel'in beklediği şekilde dışa aktarılır (genelde `app = application`).
- Statik dosyalar WhiteNoise ile servis edilir; `collectstatic`'in build sırasında nasıl çalışacağı dokümana göre ayarlanır.
- Vercel ortam değişkenleri dashboard'dan girilir; `DEBUG=False`.
- Fonksiyon süre sınırı nedeniyle uzun süren istek (long-polling) **kullanılmaz**; tüm endpoint'ler hızlı döner.

---

## 5. Klasör Yapısı (hedef)

```
triwar/
├── manage.py
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
├── TRIWAR_PLAN.md
├── triwar/                  # Django proje ayarları
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/                # Özel kullanıcı modeli, kayıt/giriş
├── game/                    # Odalar, maçlar, turlar, cevaplar
│   ├── models.py
│   ├── views.py             # Sayfa view'ları
│   ├── api.py               # JSON endpoint'leri
│   ├── engine.py            # Maç durum makinesi (lazy ilerletme)
│   ├── challenges/
│   │   ├── __init__.py      # Mücadele türü kayıt defteri (registry)
│   │   ├── base.py          # Ortak arayüz
│   │   └── country_map.py   # Ülke Bulmaca
│   ├── fixtures/countries.json
│   └── tests/
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── accounts/ (register.html, login.html)
│   └── game/ (lobby.html, room_wait.html, match.html, result.html, practice.html)
├── static/
│   ├── css/main.css
│   ├── js/api.js            # fetch + CSRF yardımcıları
│   ├── js/lobby.js
│   ├── js/room_wait.js
│   ├── js/match.js
│   ├── js/map.js            # SVG harita boyama
│   └── maps/world.svg
└── scripts/
    └── build_world_svg.py   # Natural Earth verisinden SVG + ülke fixture'ı üretir
```

---

## 6. Veri Modeli

### `accounts.User` (özel kullanıcı modeli — projenin en başında oluşturulmalı)
- `AbstractUser`'dan türetilir.
- `email`: unique, zorunlu. Giriş e-posta + şifre ile yapılır (`USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = ["username"]`).
- `username`: unique, 3–20 karakter, harf/rakam/alt çizgi. **Uygulamada herkese görünen tek kimlik budur.** E-posta hiçbir sayfada veya API yanıtında başka kullanıcılara gösterilmez.

### `game.Country`
| Alan | Tip | Not |
|---|---|---|
| `iso2` | char(2), PK | SVG'deki `path id` ile aynı |
| `name_tr` | char | Türkçe ad (cevap seçeneklerinde gösterilir) |
| `name_en` | char | |
| `continent` | char | Çeldirici seçimi için |
| `is_active` | bool | Soru havuzunda olup olmadığı |

### `game.Match` (oda ve maç tek modeldir)
| Alan | Tip | Not |
|---|---|---|
| `id` | UUID | URL'lerde kullanılır |
| `host` | FK User | Odayı kuran |
| `guest` | FK User, null | Katılan |
| `challenge_type` | char (choices) | Şimdilik `country_map` |
| `time_limit` | int (choices: 20, 45) | Soru başına saniye |
| `status` | char | `waiting` → `active` → `finished` / `cancelled` |
| `total_rounds` | int | Varsayılan 10 (ayarlardan sabit) |
| `current_round` | int | 0 tabanlı |
| `winner` | FK User, null | Beraberlikte null |
| `host_last_seen`, `guest_last_seen` | datetime | Terk tespiti (Faz 5) |
| `created_at`, `started_at`, `finished_at` | datetime | |

### `game.Round`
| Alan | Tip | Not |
|---|---|---|
| `match` | FK Match | |
| `index` | int | |
| `payload` | JSON | Client'a gidecek soru verisi (örn. `{"iso2": "PE", "options": [...]}`) — **doğru cevabı içermez** |
| `answer_key` | JSON | Doğru cevap — yalnızca sunucuda |
| `started_at` | datetime | |
| `deadline` | datetime | `started_at + time_limit` |
| `closed_at` | datetime, null | İki oyuncu da cevaplayınca veya süre bitince |

Benzersizlik: (`match`, `index`).

### `game.Answer`
| Alan | Tip | Not |
|---|---|---|
| `round` | FK Round | |
| `user` | FK User | |
| `value` | char | Seçilen cevap |
| `is_correct` | bool | |
| `response_ms` | int | `answered_at - round.started_at` |
| `answered_at` | datetime | |

Benzersizlik: (`round`, `user`) — bir oyuncu bir tura bir kez cevap verir.

### Mücadele türü arayüzü (`game/challenges/base.py`)

```python
class Challenge:
    key: str            # "country_map"
    label: str          # "Ülke Bulmaca"

    def generate_rounds(self, count: int) -> list[tuple[dict, dict]]:
        """(payload, answer_key) çiftleri döner. Aynı maçta tekrar eden soru olmaz."""

    def check_answer(self, answer_key: dict, value: str) -> bool:
        ...
```

`game/challenges/__init__.py` içindeki `REGISTRY = {"country_map": CountryMapChallenge()}` sözlüğü, oda kurma formundaki seçenekleri ve maç motorunu besler.

---

## 7. Oyun Kuralları (Ülke Bulmaca, prototip)

- Maç **10 tur**dur (sabit `ROUNDS_PER_MATCH`, ileride değiştirilebilir).
- Her turda dilsiz haritada bir ülke vurgulanır. Oyuncu **4 seçenekten** (1 doğru + 3 çeldirici) birini seçer. Çeldiriciler mümkünse aynı kıtadan seçilir.
- Her iki oyuncu aynı soruyu aynı anda görür.
- Tur, **iki oyuncu da cevapladığında** veya **süre dolduğunda** kapanır. Süre sonrası gelen cevap reddedilir (sunucu `deadline`'a göre karar verir, küçük bir ağ toleransı: 1 sn).
- Tur kapandıktan sonra **3 saniyelik gösterim aşaması**: doğru cevap ve iki oyuncunun cevabı gösterilir, sonra sonraki tur başlar (sonraki turun `started_at = closed_at + 3 sn`).
- **Puanlama:** doğru cevap = 1 puan. Maç sonunda puanı yüksek olan kazanır. Eşitlikte, doğru cevaplardaki **toplam cevap süresi** düşük olan kazanır. O da eşitse berabere.
- Bir kullanıcının aynı anda yalnızca **bir** `waiting` veya `active` maçı olabilir.
- Kullanıcı kendi odasına katılamaz.

### Maç durum makinesi (`engine.py`)

`advance(match)` fonksiyonu her state/answer isteğinde, kilitli satır üzerinde çağrılır:
1. `status != active` ise hiçbir şey yapma.
2. Mevcut tur açık ve (`now >= deadline` veya iki cevap da var) ise turu kapat (`closed_at = now` veya `deadline`).
3. Tur kapalı ve `now >= closed_at + 3 sn` ise: son turdaysa maçı bitir (kazananı hesapla), değilse `current_round += 1`.
4. Turlar maç başlarken topluca üretilir (`generate_rounds`), her turun `started_at`/`deadline`'ı o tura geçilince yazılır.

Motor saf fonksiyonlara ayrılmalı ve `now` parametre olarak verilebilmeli ki zaman bağımlı testler yazılabilsin.

---

## 8. Sayfalar ve Endpoint'ler

### Sayfalar (Django template)
| URL | Sayfa | Erişim |
|---|---|---|
| `/` | Karşılama (giriş yapılmışsa lobiye yönlendir) | Herkes |
| `/register/` | Kayıt: e-posta, kullanıcı adı, şifre, şifre tekrar | Misafir |
| `/login/`, `/logout/` | Giriş / çıkış | |
| `/lobby/` | Açık odalar listesi + "Oda Kur" formu | Giriş gerekli |
| `/room/<uuid>/` | Bekleme ekranı (host) | Giriş gerekli |
| `/match/<uuid>/` | Maç ekranı | Yalnızca o maçın oyuncuları |
| `/match/<uuid>/result/` | Sonuç ekranı | Yalnızca oyuncular |
| `/practice/` | Tek kişilik harita testi (Faz 3, geliştirme amaçlı) | Giriş gerekli |

### JSON API (hepsi giriş gerektirir, CSRF korumalı)
| Metot | URL | Açıklama |
|---|---|---|
| GET | `/api/rooms/` | `waiting` odaları: `id, host_username, challenge_label, time_limit, created_at` |
| POST | `/api/rooms/` | Oda kur: `{challenge_type, time_limit}` |
| POST | `/api/rooms/<id>/join/` | Katıl (atomic; dolu ise 409) |
| POST | `/api/rooms/<id>/cancel/` | Host odayı iptal eder (yalnızca `waiting`) |
| GET | `/api/matches/<id>/state/` | Maç durumu (aşağıda) |
| POST | `/api/matches/<id>/answer/` | `{round_index, value}` |

### `state` yanıt örneği

```json
{
  "status": "active",
  "server_now": "2026-10-25T12:00:05.120Z",
  "challenge_type": "country_map",
  "time_limit": 20,
  "round": {
    "index": 3,
    "total": 10,
    "phase": "question",
    "started_at": "...",
    "deadline": "...",
    "payload": {"iso2": "PE", "options": ["Peru", "Bolivya", "Ekvador", "Şili"]},
    "my_answer": null,
    "opponent_answered": true
  },
  "reveal": null,
  "players": {
    "me": {"username": "deniz", "score": 2},
    "opponent": {"username": "kaan", "score": 3}
  }
}
```

- `phase`: `question` veya `reveal`. `reveal` aşamasında `reveal` alanı doğru cevabı ve iki oyuncunun cevabını içerir.
- Client, `server_now` ile kendi saati arasındaki farkı hesaplayıp geri sayımı buna göre gösterir.
- Yanıtlarda e-posta veya başka özel bilgi **olmaz**.

---

## 9. Harita

- Kaynak: **Natural Earth Admin 0 Countries (1:110m)** — kamu malı (public domain). `scripts/build_world_svg.py` GeoJSON'u okuyup basit bir projeksiyonla (equirectangular yeterli; istenirse Robinson/Natural Earth projeksiyonu) `static/maps/world.svg` üretir. Antarktika hariç tutulur.
- Her ülke `<path id="ISO2" class="country">` şeklindedir. **Dikkat:** Natural Earth'te bazı ülkelerde `ISO_A2 = -99` (örn. Fransa, Norveç); bu durumda `ISO_A2_EH` alanı kullanılmalı. Kodu olmayan bölgeler sorulmaz ama haritada gri kalır.
- Aynı script `game/fixtures/countries.json` dosyasını da üretir (`iso2`, `name_en`, `name_tr` = Natural Earth `NAME_TR` alanı, `continent`). Türkçe adlar bir kez gözden geçirilmeli.
- Çok küçük ülkeler (alan eşiğinin altı) `is_active = False` ile başlar; soru havuzu prototipte orta-büyük ülkelerden oluşur.
- SVG sayfaya **inline** gömülür (CSS ile renklendirilebilmesi için).
- `map.js`: `highlight(iso2)` hedef ülkeyi vurgu rengiyle boyar; ülke küçükse (`getBBox()` eşiğin altında) etrafına nabız animasyonlu bir halka çizer.
- Ülke üzerine gelince isim tooltip'i **gösterilmez** (cevabı ele verir).

---

## 10. Arayüz Tasarımı

**Hedef his:** genç, enerjik, temiz. Açık arka plan, canlı renkler, bol boşluk, yuvarlak köşeler.

### Renk paleti (CSS değişkenleri olarak `:root`'ta)
```css
--bg: #F7F7FC;          /* açık, hafif soğuk arka plan */
--surface: #FFFFFF;
--text: #1E1B3A;
--text-muted: #6B6890;
--primary: #7C3AED;     /* canlı mor */
--primary-tint: #EDE4FF;
--accent: #FF4D8D;      /* pembe — haritada hedef ülke */
--accent-tint: #FFE3EE;
--cyan: #06B6D4;
--cyan-tint: #DDF7FC;
--yellow: #FFC83D;
--success: #22C55E;
--danger: #EF4444;
--map-land: #E4E3F0;
--map-border: #FFFFFF;
--map-ocean: #EAF6FF;
```
- "Renk tonları" yaklaşımı: kartlar ve rozetler canlı rengin açık tonu (`*-tint`) zeminine aynı rengin koyu yazısıyla. Butonlar dolu canlı renk; hover'da hafif yükselme + gölge.
- Mücadele türü ve süre için rozetler: `Ülke Bulmaca` (mor ton), `20 sn` (pembe ton), `45 sn` (cyan ton).

### Tipografi
- Başlıklar: **Fredoka** (Google Fonts) — yuvarlak, oyunsu.
- Gövde: **Nunito**.
- Fallback: `system-ui, sans-serif`.

### Bileşen kuralları
- Köşe yarıçapı 16–20px, yumuşak gölgeler (`0 8px 24px rgb(124 58 237 / 0.10)`).
- Maç ekranında geri sayım dairesel bir ilerleme halkası olarak; son 5 saniyede pembe/kırmızıya döner.
- Cevap butonları 2x2 ızgara, büyük ve dokunmaya uygun; seçildiğinde kilitlenir, gösterim aşamasında doğru yeşil, yanlış kırmızı olur.
- Skor tablosu üstte: `deniz 3 — 2 kaan`.
- Mobil öncelikli, responsive (harita genişliğe sığar, butonlar alta).
- Mikro animasyonlar hafif tutulur (`prefers-reduced-motion`'a saygı).
- Arayüz dili: **Türkçe**.

---

## 11. Claude Code Çalışma Kuralları

1. Her oturumda önce bu dosyayı oku; yalnızca istenen fazı uygula, sonraki fazlara ait özellik ekleme.
2. Plandan sapman gerekirse (teknik engel, daha basit bir yol) önce kısaca açıkla ve onay iste.
3. Yeni bağımlılık eklemeden önce sor.
4. Her faz sonunda: testleri çalıştır, kabul kriterlerini tek tek kontrol et, bu dosyadaki "Faz Durumu" tablosunu güncelle ve yapılanları kısaca özetle.
5. Gizli bilgileri (şifreler, bağlantı dizeleri) asla koda veya commit'e yazma.
6. Kod ve yorumlar İngilizce, kullanıcıya görünen metinler Türkçe.
7. Basit tut: prototipteyiz.

---

## 12. Fazlar

### Faz Durumu
| Faz | Konu | Durum |
|---|---|---|
| 0 | İskelet, Supabase bağlantısı, Vercel'e ilk deploy | ✅ |
| 1 | Kayıt / giriş / çıkış | ✅ |
| 2 | Lobi ve odalar | ✅ |
| 3 | Harita ve ülke verisi (tek kişilik test) | ✅ |
| 4 | 1v1 maç akışı | ⬜ |
| 5 | Sonuç ekranı, terk/temizlik, cila | ⬜ |

---

### Faz 0 — İskelet ve Altyapı

**Hedef:** Boş ama canlıda çalışan bir Django projesi, Supabase'e bağlı.

**Görevler**
- Django projesi (`triwar`) ve `accounts`, `game` uygulamaları.
- **Özel kullanıcı modeli** (`accounts.User`) ilk migration'dan önce tanımlanır.
- `settings.py`: env değişkenleri, `dj-database-url`, pooler ayarları (Bölüm 3), WhiteNoise, `LANGUAGE_CODE="tr"`, `TIME_ZONE="Europe/Istanbul"`, `USE_TZ=True`.
- `base.html` + `main.css` (palet, fontlar, temel bileşenler) + basit karşılama sayfası.
- RLS etkinleştiren migration.
- `vercel.json` ve WSGI giriş noktası (güncel Vercel dokümanına göre).
- `.env.example`, `.gitignore`, `README.md` (lokal kurulum + migrate + deploy adımları).

**Kabul kriterleri**
- `python manage.py runserver` ile karşılama sayfası lokal açılıyor.
- `migrate` Supabase'e uygulanıyor; Supabase Advisors'ta RLS uyarısı yok.
- Vercel'deki URL'de karşılama sayfası stilleriyle birlikte açılıyor.
- `/admin/` çalışıyor (superuser ile giriş).

**Claude Code promptu**
```
TRIWAR_PLAN.md dosyasını oku. Yalnızca Faz 0'ı uygula: Django iskeleti, özel kullanıcı
modeli, Supabase bağlantısı (transaction pooler ayarlarıyla), RLS migration'ı, temel
tasarım sistemi (base.html + main.css) ve Vercel deploy yapılandırması. Vercel
yapılandırmasını yazmadan önce güncel Vercel Django/Python dokümantasyonunu kontrol et.
Bitince kabul kriterlerini kontrol et, README'yi yaz ve Faz Durumu tablosunu güncelle.
```

---

### Faz 1 — Kimlik Doğrulama

**Hedef:** Kullanıcı kayıt olabilir, giriş/çıkış yapabilir.

**Görevler**
- Kayıt formu: e-posta, kullanıcı adı, şifre, şifre tekrar. Django şifre doğrulayıcıları. E-posta ve kullanıcı adı benzersizliği (büyük/küçük harf duyarsız).
- Giriş: e-posta + şifre. Çıkış POST ile.
- Hata mesajları Türkçe ve form altında, tasarıma uygun.
- Giriş yapmış kullanıcı üst menüde yalnızca kullanıcı adını görür.
- `login_required` ile korunan boş bir `/lobby/` sayfası (Faz 2'de doldurulacak).
- Testler: kayıt, tekrar eden e-posta/kullanıcı adı, giriş, çıkış.

**Kabul kriterleri**
- Yeni kullanıcı kaydolup otomatik giriş yapıyor ve lobiye yönleniyor.
- Aynı e-posta / kullanıcı adıyla ikinci kayıt anlamlı hata veriyor.
- Giriş yapmamış kullanıcı `/lobby/`'ye girince login'e yönleniyor.

**Claude Code promptu**
```
TRIWAR_PLAN.md dosyasını oku. Faz 1'i uygula: kayıt (e-posta, kullanıcı adı, şifre),
e-posta ile giriş, çıkış ve korumalı boş lobi sayfası. Formlar Bölüm 10'daki tasarıma
uygun olsun. Testleri yaz ve çalıştır, kabul kriterlerini kontrol et, Faz Durumu
tablosunu güncelle.
```

---

### Faz 2 — Lobi ve Odalar

**Hedef:** Kullanıcılar oda kurabilir, açık odaları görebilir, birbirinin odasına katılabilir.

**Görevler**
- `Match` modeli (Bölüm 6) ve mücadele türü kayıt defteri iskeleti (`country_map` kayıtlı, `generate_rounds` henüz basit/boş olabilir).
- Lobi: "Oda Kur" kartı (mücadele türü seçimi + 20/45 sn seçimi) ve açık odalar listesi (kart görünümü: host kullanıcı adı, tür rozeti, süre rozeti, "Katıl" butonu).
- `lobby.js`: `/api/rooms/`'u 3 sn'de bir sorgular, listeyi yeniler. Sekme görünür değilken polling durur (`visibilitychange`).
- Oda kurunca host `/room/<id>/` bekleme ekranına gider ("Rakip bekleniyor…" animasyonu, oda bilgileri, "İptal" butonu). `room_wait.js` 2 sn'de bir durumu sorgular; maç `active` olunca `/match/<id>/`'ye yönlendirir.
- Katılma işlemi `select_for_update` ile atomik; aynı anda iki kişi katılmaya çalışırsa biri 409 alır ve "Oda doldu" mesajı görür.
- Kurallar: kullanıcı kendi odasına katılamaz, aynı anda tek `waiting`/`active` maç.
- Maç `active` olduğunda şimdilik `/match/<id>/` basit bir "Maç başladı: deniz vs kaan" sayfası gösterir.
- Testler: oda kurma, listeleme (e-posta sızmıyor), katılma, eşzamanlı katılma, iptal, kurallar.

**Kabul kriterleri**
- İki farklı tarayıcıda (biri gizli pencere) iki kullanıcı: biri oda kuruyor, diğeri lobide birkaç saniye içinde görüp katılıyor, ikisi de maç sayfasına geçiyor.
- API yanıtlarında e-posta yok.

**Claude Code promptu**
```
TRIWAR_PLAN.md dosyasını oku. Faz 2'yi uygula: Match modeli, mücadele türü registry
iskeleti, lobi (oda kurma + polling ile oda listesi), bekleme ekranı, atomik katılma
ve iptal. Maç başladığında şimdilik basit bir yer tutucu maç sayfası göster. Testleri
yaz ve çalıştır, kabul kriterlerini kontrol et, Faz Durumu tablosunu güncelle.
```

---

### Faz 3 — Harita ve Ülke Verisi

**Hedef:** Dilsiz dünya haritası ve ülke soru havuzu hazır; tek kişilik test sayfasında doğrulanmış.

**Görevler**
- `scripts/build_world_svg.py` (Bölüm 9): Natural Earth 110m verisinden `world.svg` ve `countries.json` üretir. Script yalnızca standart kütüphane kullanmalı (gerekirse sor). İndirilen ham veri repoya eklenmez; üretilen SVG ve fixture eklenir.
- `Country` modeli + fixture yükleme (`loaddata`).
- `CountryMapChallenge`: `generate_rounds` (tekrarsız, 4 seçenek, aynı kıtadan çeldirici tercih) ve `check_answer`.
- `map.js`: inline SVG'de `highlight(iso2)`, küçük ülkeler için halka.
- `/practice/`: tek kişilik deneme — rastgele ülke, 4 seçenek, seçimden sonra doğru/yanlış gösterimi, "Sonraki". (Süre yok; amaç harita ve veriyi doğrulamak.)
- Testler: `generate_rounds` tekrarsızlık, seçenek sayısı, doğru cevabın seçenekler içinde olması, `check_answer`.

**Kabul kriterleri**
- Harita mobil ve masaüstünde düzgün ölçekleniyor, ülke sınırları seçiliyor.
- Practice sayfasında 20 soru boyunca vurgulanan ülke ile doğru cevap tutarlı (Fransa, Norveç dahil).
- Türkçe ülke adları doğru görünüyor.

**Claude Code promptu**
```
TRIWAR_PLAN.md dosyasını oku. Faz 3'ü uygula: Natural Earth 110m verisinden dilsiz
dünya haritası SVG'si ve ülke fixture'ı üreten script, Country modeli,
CountryMapChallenge (generate_rounds, check_answer), map.js ve /practice/ test sayfası.
ISO_A2 = -99 olan ülkelere dikkat et. Testleri yaz ve çalıştır, kabul kriterlerini
kontrol et, Faz Durumu tablosunu güncelle.
```

---

### Faz 4 — 1v1 Maç Akışı

**Hedef:** İki oyuncu baştan sona bir maç oynayabilir.

**Görevler**
- `Round` ve `Answer` modelleri.
- Maç başlarken (`join` anında) turlar `generate_rounds` ile üretilir, ilk tur `started_at = now + 3 sn` (geri sayım "3-2-1" için).
- `engine.py`: Bölüm 7'deki durum makinesi; saf, `now` parametreli, `select_for_update` ile çağrılır.
- `/api/matches/<id>/state/` ve `/answer/` (Bölüm 8). Cevap: tur indeksi doğrulaması, süre kontrolü, tek cevap kuralı, `response_ms` hesabı.
- `match.html` + `match.js`: 1 sn polling, `server_now` ile saat farkı düzeltmesi, dairesel geri sayım, harita vurgusu, 2x2 cevap butonları, "Rakip cevapladı" göstergesi, gösterim aşaması, skor tablosu. Maç `finished` olunca sonuç sayfasına yönlendir.
- Sonuç sayfası (basit): kazanan, skorlar, "Lobiye dön".
- Testler (zaman parametreli): tur kapanışı (iki cevap / süre dolması), geç cevap reddi, çift cevap reddi, tur geçişi, maç bitişi, eşitlik bozma kuralı, doğru cevabın `question` aşamasında sızmaması.

**Kabul kriterleri**
- İki tarayıcıda 10 turluk maç sorunsuz tamamlanıyor; 20 sn ve 45 sn seçenekleri doğru uygulanıyor.
- Bir oyuncu cevap vermezse tur süre sonunda kapanıyor ve maç devam ediyor.
- İki taraf da aynı skoru ve aynı kazananı görüyor.
- Ağ sekmesinde, tur bitmeden doğru cevap hiçbir yanıtta görünmüyor.

**Claude Code promptu**
```
TRIWAR_PLAN.md dosyasını oku. Faz 4'ü uygula: Round ve Answer modelleri, Bölüm 7'deki
lazy maç motoru (engine.py), state ve answer API'leri, maç ekranı (polling, sunucu
saatine göre geri sayım, harita, cevap butonları, gösterim aşaması, skor) ve basit
sonuç sayfası. Motoru zaman parametreli testlerle kapsamlı test et. Kabul kriterlerini
kontrol et, Faz Durumu tablosunu güncelle.
```

---

### Faz 5 — Sağlamlaştırma ve Cila

**Hedef:** Prototip gerçek kullanıcılara gösterilebilir hale gelir.

**Görevler**
- **Terk tespiti:** state isteklerinde `*_last_seen` güncellenir; bir oyuncu 30 sn görünmezse maç rakip lehine biter (sonuçta "rakip ayrıldı").
- **Bayat odalar:** 10 dakikadan eski `waiting` odalar lobi sorgusunda otomatik `cancelled` olur.
- Bekleme ekranından ayrılan host'un odası iptal edilir (`pagehide` + `navigator.sendBeacon`; yedek olarak bayatlık kuralı).
- Sonuç ekranını zenginleştir: tur tur özet (ülke, iki oyuncunun cevabı, süre).
- Basit profil/istatistik: galibiyet / mağlubiyet / beraberlik sayısı (lobide kullanıcı adının yanında).
- Boş durumlar (lobide oda yok), yükleme ve hata durumları, 404/403 sayfaları.
- Erişilebilirlik: klavyeyle cevap verme (1–4 tuşları), yeterli kontrast, `prefers-reduced-motion`.
- Basit hız sınırlama (örn. oda kurma) — ek bağımlılık olmadan.

**Kabul kriterleri**
- Maç ortasında sekmeyi kapatan oyuncu ~30 sn içinde hükmen kaybediyor.
- Lobide eski/terk edilmiş oda kalmıyor.
- Mobilde tüm akış (kayıt → oda → maç → sonuç) rahatça oynanıyor.

**Claude Code promptu**
```
TRIWAR_PLAN.md dosyasını oku. Faz 5'i uygula: terk tespiti ve hükmen galibiyet, bayat
oda temizliği, tur tur sonuç özeti, basit G/M/B istatistiği, boş/hata durumları,
klavye kısayolları ve erişilebilirlik iyileştirmeleri. Testleri güncelle, kabul
kriterlerini kontrol et, Faz Durumu tablosunu güncelle.
```

---

## 13. Sonraki Adımlar (kapsam dışı, ileride konuşulacak)

- Yeni mücadele türleri (bayraklar, başkentler, vb.) — registry'ye yeni modül eklenerek.
- Serbest metinle cevap (alternatif adlar + Türkçe karakter normalizasyonu).
- Polling yerine Supabase Realtime.
- Hızlı eşleşme (oda kurmadan rastgele rakip), arkadaş davet linki.
- ELO/puan sistemi ve liderlik tablosu.
- Zorluk seviyeleri (küçük ülkeleri havuza alma), harita yakınlaştırma.
- E-posta doğrulama ve şifre sıfırlama.
