# API Review dan Rating GAIA

API DRF untuk integrasi Flutter menggunakan model `Review`, `ReviewReport`, dan
`AccountOrder` yang sudah digunakan website. Base path: `/api/reviews/`.
Seluruh respons endpoint ini berformat JSON, kecuali `204 No Content` tanpa body.
Endpoint HTML `/reviews/` tetap tersedia. Tidak ada perubahan model atau migration.

## Autentikasi dan CSRF

API menggunakan **Django SessionAuthentication**. Klien harus menyimpan cookie
`sessionid` dan `csrftoken` dalam cookie jar yang sama pada seluruh request.
Semua POST, PUT, PATCH, dan DELETE yang terautentikasi membutuhkan header
`X-CSRFToken`. GET publik dapat digunakan tanpa login.

1. GET `/api/reviews/csrf/` untuk mendapatkan cookie CSRF dan JSON
   `{"csrfToken":"<token>"}`.
2. Login melalui endpoint akun website yang sudah ada, POST `/accounts/login/`
   sebagai **form URL encoded**, dengan `username`, `password`, dan
   `csrfmiddlewaretoken`. Field `username` mengikuti form login website
   (menerima username atau email akun). Login ini mengembalikan redirect HTML;
   bukan endpoint login JSON baru. Simpan cookie session hasil login.
3. GET `/api/reviews/csrf/` kembali setelah login karena Django merotasi token.
4. Kirim JSON dengan `Content-Type: application/json`, cookie session dan CSRF,
   serta header `X-CSRFToken: <token-terbaru>` untuk operasi tulis.

Untuk Flutter gunakan satu cookie jar/client yang sama, termasuk ketika mengambil
token. GET CSRF saja tidak melakukan login. Jika modul akun nanti menyediakan
login mobile yang menghasilkan Django session, session itu dapat langsung
digunakan di sini. Integrasi autentikasi akun dan perubahan Flutter tidak termasuk
perubahan modul review ini. Flutter Web di origin berbeda memerlukan konfigurasi
deployment CORS, trusted origin, dan kebijakan cookie yang sesuai; konfigurasi
lintas origin tersebut belum ditambahkan.

SessionAuthentication mengembalikan **403** untuk belum login, session tidak valid,
CSRF gagal, atau izin tidak cukup. Tidak ada redirect ke halaman login pada API.
Perilaku ini mengikuti [dokumentasi autentikasi DRF](https://www.django-rest-framework.org/api-guide/authentication/).

## Daftar endpoint

Semua path berikut relatif terhadap `/api/reviews/` dan memakai trailing slash.
`id` adalah ID review; `seller_id` adalah ID user penjual.

| Path | Metode | Akses | Hasil berhasil |
| --- | --- | --- | --- |
| `/` | GET | Publik | 200 daftar review dengan pagination |
| `/` | POST | Login, pemilik pesanan eligible | 201 objek review baru |
| `/<id>/` | GET | Publik | 200 objek review |
| `/<id>/` | PUT, PATCH | Penulis review | 200 objek review setelah edit |
| `/<id>/` | DELETE | Penulis review | 204 tanpa body |
| `/mine/` | GET | Login | 200 review yang ditulis pengguna saat ini |
| `/seller/<seller_id>/` | GET | Publik, penjual aktif yang valid | 200 daftar review penjual |
| `/seller/<seller_id>/summary/` | GET | Publik, penjual aktif yang valid | 200 rata-rata dan distribusi rating |
| `/seller/<seller_id>/eligible-orders/` | GET | Login | 200 pesanan sendiri yang dapat direview untuk penjual ini |
| `/<id>/helpful/` | POST | Login, selain penulis dan penjual terkait | 200 toggle helpful |
| `/<id>/reply/` | POST | Penjual yang direview | 200 objek review dengan balasan baru/diperbarui |
| `/<id>/reply/` | DELETE | Penjual yang direview | 200 objek review dengan balasan kosong |
| `/<id>/report/` | POST | Login, selain penulis review | 201 laporan baru; 200 jika sudah pernah melapor |
| `/csrf/` | GET | Publik | 200 token CSRF dan cookie |

GET collection mendukung `page` (default 1) dan `page_size` (default 6, maksimum
100). Collection review juga mendukung `rating=1..5`, `seller=<id>`, dan
`sort=newest|helpful|rating` (default `newest`). Path seller menentukan seller jika
query `seller` juga diberikan. Filter invalid menghasilkan 400; halaman tidak
tersedia menghasilkan 404. Summary selalu menghitung seluruh review penjual,
terlepas dari filter pada daftar.

## Aturan pembuatan dan edit

- Pesanan wajib benar-benar ada, berstatus `completed`, dimiliki pengguna yang
  login, memiliki penjual aktif, dan belum memiliki review.
- Tidak boleh mereview diri sendiri. Pesanan historis tanpa seller tidak eligible.
- Satu pesanan hanya memiliki satu review. Pembelian terpisah dapat direview
  masing-masing. Penghapusan review membuat pesanan eligible kembali.
- `reviewer` selalu berasal dari `request.user`. `seller` diturunkan dari pesanan.
  Payload yang mengirim identitas atau field di luar kontrak ditolak dengan 400.
- `rating` wajib bernilai integer 1–5. `title` wajib, maksimum 100 karakter;
  `comment` wajib, maksimum 2000 karakter. Teks kosong/spasi ditolak.
- Flag opsional: `is_anonymous`, `is_friendly`, `is_responsive`,
  `is_trustworthy` (default false pada pembuatan).
- PUT membutuhkan `rating`, `title`, dan `comment`; PATCH boleh mengirim hanya
  field yang diubah. `order`, reviewer, seller, balasan, helpful, dan metadata
  server tidak dapat diubah melalui PUT/PATCH review.
- Pemeriksaan pesanan dilakukan kembali dalam transaksi dengan row lock;
  constraint unik model yang sudah ada mencegah review duplikat. Konflik saat
  penyimpanan diterjemahkan menjadi validation error JSON.

## Contoh request dan respons

### Membuat review

POST `/api/reviews/` dengan session dan header CSRF:

```json
{
  "order": 42,
  "rating": 5,
  "title": "Seller ramah",
  "comment": "Komunikasi cepat dan barang sesuai deskripsi.",
  "is_anonymous": false,
  "is_friendly": true,
  "is_responsive": true,
  "is_trustworthy": true
}
```

Contoh respons 201 berikut untuk penulis yang login; ID dan waktu adalah ilustrasi:

```json
{
  "id": 7,
  "order": 42,
  "reviewer": 3,
  "reviewer_name": "Pembeli GAIA",
  "seller": 2,
  "rating": 5,
  "title": "Seller ramah",
  "comment": "Komunikasi cepat dan barang sesuai deskripsi.",
  "is_anonymous": false,
  "is_friendly": true,
  "is_responsive": true,
  "is_trustworthy": true,
  "helpful_count": 0,
  "has_voted": false,
  "has_reported": false,
  "is_owner": true,
  "can_reply": false,
  "is_verified_purchase": true,
  "seller_reply": "",
  "seller_replied_at": null,
  "created_at": "2026-11-20T08:00:00Z",
  "updated_at": "2026-11-20T08:00:00Z"
}
```

Respons GET detail, edit, dan balasan memakai struktur review yang sama. Daftar
review membungkus objek tersebut dalam `results`:

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}
```

`next` dan `previous` adalah URL halaman atau null. Contoh daftar pesanan eligible:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {"id": 42, "number": "GAIA-42", "seller": 2, "product": 10,
     "title": "Vintage coat", "date": "2026-11-20", "status": "completed"}
  ]
}
```

### Mengedit dan menghapus review

PATCH `/api/reviews/7/`:

```json
{"rating": 4, "comment": "Pengalaman belanja baik."}
```

Respons 200 berupa objek review terbaru. DELETE `/api/reviews/7/` menghasilkan
204 tanpa body. Klien tidak perlu melakukan JSON decode pada respons 204.

### Summary rating

GET `/api/reviews/seller/2/summary/`, contoh respons 200 untuk satu review bintang 5:

```json
{
  "seller": 2,
  "average_rating": 5.0,
  "total_reviews": 1,
  "rating_breakdown": [
    {"rating": 5, "count": 1, "percent": 100},
    {"rating": 4, "count": 0, "percent": 0},
    {"rating": 3, "count": 0, "percent": 0},
    {"rating": 2, "count": 0, "percent": 0},
    {"rating": 1, "count": 0, "percent": 0}
  ]
}
```

Penjual tanpa review menghasilkan `average_rating: null`, `total_reviews: 0`,
dan breakdown bernilai nol.

### Helpful, balasan, dan laporan

POST `/api/reviews/7/helpful/` dengan body `{}`:

```json
{"has_voted": true, "helpful_count": 1}
```

POST berikutnya menghapus vote dan mengembalikan `has_voted: false` beserta
jumlah terbaru. Operasi toggle ini tidak idempotent.

POST `/api/reviews/7/reply/`:

```json
{"reply": "Terima kasih sudah berbelanja!"}
```

Balasan wajib berisi teks, maksimum 1000 karakter. Respons 200 adalah objek review
dengan `seller_reply` dan timestamp `seller_replied_at`. DELETE pada path yang sama
mengosongkan balasan dan mengembalikan timestamp null.

POST `/api/reviews/7/report/`:

```json
{"reason": "spam", "details": "Konten promosi berulang."}
```

`reason` wajib berupa `spam`, `offensive`, `privacy`, atau `other`; `details`
opsional maksimum 1000 karakter. Respons 201 untuk laporan pertama:

```json
{"has_reported": true}
```

Laporan berulang oleh pengguna yang sama menghasilkan 200 dengan body yang sama
dan mempertahankan laporan pertama. Tidak ada endpoint publik untuk membaca
identitas pelapor atau isi laporan.

## Privasi dan error

Untuk pengunjung belum login, `reviewer` bernilai null dan `reviewer_name`
adalah `GAIA member`. Untuk review anonim, `reviewer` selalu null dan namanya
`Anonymous`, termasuk untuk pengguna yang login. `order` hanya terlihat oleh
penulis review; pengguna lain menerima null. Gunakan `is_owner` untuk kontrol
edit/hapus, dan `can_reply` untuk kontrol penjual. API tetap memeriksa izin server.
Semua respons API memakai `Cache-Control: private, no-store`.

Contoh 400 rating tidak valid:

```json
{"rating": ["Ensure this value is less than or equal to 5."]}
```

Contoh 400 untuk pesanan tidak eligible, termasuk pesanan pengguna lain:

```json
{"order": ["This order is not eligible for a review."]}
```

Contoh 403 belum login:

```json
{"detail": "Authentication credentials were not provided."}
```

Izin ditolak juga memakai `{"detail":"..."}` dengan status 403; objek hilang 404;
metode tidak didukung 405. JSON rusak dan payload selain objek menghasilkan 400.
Pesan error DRF dapat mengikuti bahasa server; klien harus mengandalkan status
HTTP dan nama field, bukan membandingkan teks pesan.

## File dan verifikasi

File baru: `reviews/serializers.py`, `reviews/api_views.py`, `reviews/api_urls.py`,
`reviews/test_api.py`, dan `docs/reviews-api.md`. Konfigurasi yang diubah:
`requirements.txt` (pin DRF 3.18.3), `gaia/settings.py` (INSTALLED_APPS), dan
`gaia/urls.py` (include API). HTML views, URL website, forms, model, dan modul
anggota lain tidak diubah.

Jalankan dari root Django dengan virtual environment `env`:

```powershell
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py test reviews.test_api --noinput
.\env\Scripts\python.exe manage.py test --noinput
.\env\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Jika test upload gambar mengalami `PermissionError` pada folder sementara Windows,
arahkan environment variable `TEMP` dan `TMP` ke folder sementara yang dapat
ditulis, hanya untuk shell pengujian tersebut, lalu ulangi perintah test. Ini tidak
memerlukan perubahan konfigurasi aplikasi maupun kode modul lain.

Pengujian API meliputi pembuatan berhasil, batas rating, input tidak valid,
autentikasi session dan CSRF, login website sampai POST API, pemalsuan identitas,
pesanan tidak eligible/duplikat, konflik saat simpan, izin edit/hapus/balasan,
helpful, laporan, anonimitas, filter, pagination, summary, review historis,
dan keberlanjutan URL HTML. Test Django menggunakan database pengujian terpisah.

Hasil verifikasi implementasi pada 20 November 2026: 28 tes API lolos, 102 tes
modul reviews lolos, dan seluruh 559 tes proyek lolos. Pemeriksaan Django,
dependency (`pip check`), migration (`--check --dry-run`), dan `git diff --check`
juga lolos. Suite proyek dijalankan dengan `TEMP`/`TMP` menunjuk folder workspace
yang dapat ditulis. Verifikasi ini dilakukan secara lokal; deployment PWS dan
integrasi UI Flutter belum dijalankan.
