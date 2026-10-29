# Gaia

**Gaia** adalah platform marketplace thrifting untuk membeli dan menjual pakaian bekas layak pakai. Melalui konsep **circular fashion**, Gaia ingin memberikan pakaian kesempatan kedua sekaligus mengurangi limbah *fast fashion*.

## Fokus Pengembangan: MVP

**Saat ini, tim Gaia sedang mengembangkan Minimum Viable Product (MVP) yang terdiri dari lima modul utama: User, Product, Chat, Transaksi, serta Review & Rating.** Pengembangan tahap ini memprioritaskan penyelesaian dan integrasi kelima modul agar alur dasar marketplace dapat digunakan dari pendaftaran akun hingga pemberian review setelah transaksi.

Pembagian tanggung jawab MVP adalah **Danar: User, Kayla: Product, Deva: Chat, Salma: Transaksi, dan Keisha: Review & Rating**. Cakupan tiap modul dijelaskan pada bagian pembagian modul di bawah; seluruh fitur MVP masih dalam proses pengembangan dan penyempurnaan.

**Fitur selain kelima modul tersebut berada di luar cakupan pengembangan MVP.** Pengembangan fitur tambahan baru dilakukan setelah seluruh modul MVP selesai dikembangkan, terintegrasi, diuji, dan berjalan dengan baik. Fitur tambahan yang sudah terdapat pada kode tetap dapat dipertahankan, tetapi bukan prioritas penyelesaian tahap MVP.

[Desain Gaia di Figma](https://www.figma.com/design/gTTsLkfL1qaaPdEomnRfKf/Gaia?node-id=1-4&t=S3z03qUIKvsz1lNL-1)

---

## Anggota Kelompok
| No. | Nama                | NPM          |
| --: | ------------------- | ------------ |
|   1 | **Danar Iqbal Abi Zaidan Suharso** | `2506534371` |
|   2 | **I Gede Devadatta A.D**            | `2506622481` |
|   3 | **Keisha Janice Maulina Napitupulu**          | `2506551232` |
|   4 | **Kayla Kirana Ali Trimardhany**           | `2506603854` |
|   5 | **Salma Maharani**           | `2506586532` |

## Cakupan MVP dan Pembagian Modul

| No. | Penanggung jawab | Modul | Target pengembangan MVP |
| --: | ---------------- | ----- | ----------------------- |
| 1 | **Danar** | **User / Authentication** | Registrasi, login/logout, profil dan foto profil, keamanan serta penghapusan akun, dan wishlist produk favorit. |
| 2 | **Kayla** | **Product / Listing** | Pengelolaan listing, foto produk, kategori, harga, kondisi, status ketersediaan, detail produk, serta pencarian/filter dasar untuk menemukan produk. |
| 3 | **Deva** | **Chat / Messaging** | Percakapan dan pesan antara buyer dan seller untuk membahas produk serta transaksi. |
| 4 | **Salma** | **Transaksi** | Keranjang, checkout, pembuatan pesanan, alur pembayaran, serta pelacakan status transaksi. |
| 5 | **Keisha** | **Review & Rating** | Pemberian dan penampilan review/rating setelah transaksi, dengan pembatasan berdasarkan pihak yang bertransaksi. |

Pencarian/filter dasar menjadi bagian pendukung Product, dan keranjang menjadi bagian Transaksi. Keduanya tidak memiliki penanggung jawab modul terpisah. Wishlist dasar menjadi bagian modul User. Kelima modul dikembangkan dengan pembatasan akses sesuai peran dan kepemilikan data.

## User Roles dalam MVP

| Role | Peran dan target hak akses |
| ---- | ------------------------- |
| **Guest** | Melihat katalog, mencari produk, dan melihat detail produk; registrasi/login untuk menggunakan fitur akun. |
| **Registered User** | Dapat berperan sebagai buyer dan seller: mengelola profil/listing sendiri, menyimpan produk ke wishlist, berkomunikasi, bertransaksi, serta memberikan review/rating sesuai ketentuan transaksi. |
| **Admin** | Mengelola data melalui Django admin untuk mendukung operasional MVP. Dashboard dan moderasi lanjutan bukan bagian target MVP saat ini. |

## API dan Integrasi MVP

Integrasi berikut mendukung modul User, Transaksi, dan Chat dalam MVP. Statusnya membedakan integrasi yang sudah tersedia dari opsi yang masih direncanakan.

| API / teknologi | Status di kode saat ini | Pemakaian / tindak lanjut |
| --------------- | ----------------------- | ------------------------ |
| **Google OAuth 2.0 melalui `django-allauth`** | **Sudah terintegrasi** pada modul User. | Login Google menggunakan client ID/secret dari environment dan callback `/accounts/google/login/callback/`. Operasionalnya memerlukan konfigurasi Google Cloud dan PWS. |
| **Email Django / SMTP** | **Alur email tersedia**, default masih console backend. Ini mekanisme pengiriman email, bukan public API yang sudah terhubung ke vendor tertentu. | Email verifikasi/reset dicetak di terminal pada konfigurasi default. SMTP harus dikonfigurasi agar email benar-benar dikirim ke inbox. |
| **Midtrans / Xendit API** | **Belum digunakan**. | Opsi integrasi pembayaran untuk modul Transaksi. Provider dan penggunaan sandbox/mock perlu ditentukan saat alur transaksi dikembangkan; belum ada request gateway, callback/webhook, atau mock payment API. |
| **Django Channels / WebSocket** | **Belum digunakan**. Channels/WebSocket adalah teknologi komunikasi, bukan public API eksternal. | Opsi implementasi chat real-time; transport pesan belum ditentukan dan belum tersedia pada checkout ini. |

Data dari `seed_products`/`seed_account_demo`, snapshot order, dan konstanta rating merupakan data awal/demo, **bukan bukti integrasi API eksternal atau mock API pembayaran**. Endpoint aplikasi sendiri juga berbeda dari layanan pihak ketiga pada tabel di atas.

## Pengembangan Setelah MVP

Setelah User, Product, Chat, Transaksi, dan Review & Rating selesai serta terintegrasi dengan baik, tim dapat melanjutkan:

- Community / Social Feed dan interaksi sosial.
- Outfit Generator dan rekomendasi berbasis AI.
- Wishlist lanjutan dan notifikasi favorit; wishlist dasar sudah termasuk dalam modul User pada MVP.
- Dashboard khusus, statistik, moderasi, dan pelaporan lanjutan.
- Peta/autocomplete alamat, Lemari pribadi, serta fitur pencarian, nego, dan notifikasi lanjutan di luar kebutuhan dasar MVP.
- Integrasi tambahan seperti penyimpanan cloud sesuai kebutuhan operasional.

Fitur-fitur tersebut bukan komitmen deliverable MVP dan tidak menjadi fokus pembagian tugas tahap pertama.

---

**Gaia — A circular fashion marketplace where every piece gets a second chance.**

## Auto deploy ke PWS

Workflow `.github/workflows/deploy.yml` berjalan setiap ada push atau merge ke branch GitHub `main`, lalu mengirim commit tersebut ke branch `master` PWS Gaia. Deploy juga bisa dijalankan dari tab **Actions > Push to PWS > Run workflow**, dengan branch `main`.

Repository secret `PWS_URL` harus berisi URL Git PWS dengan kredensial proyek, dikelola melalui **Settings > Secrets and variables > Actions**. Jangan masukkan kredensial ke file repository. Workflow memakai `actions/checkout@v7`, mengambil seluruh riwayat Git, dan mengantre deployment agar tidak bertabrakan. Push tidak memakai force; riwayat PWS yang berbeda perlu disinkronkan sebelum deployment bisa lanjut.

Untuk merilis perubahan, push atau merge feature branch ke `main`, lalu cek hasil **Push to PWS** di tab Actions. Tidak perlu push PWS manual lagi. Build aplikasi tetap dijalankan oleh PWS setelah menerima push.

## Teknologi

- **Backend:** Python dan Django.
- **Frontend:** Django Templates, HTML, CSS, dan JavaScript.
- **Database:** SQLite untuk pengembangan lokal dan PostgreSQL untuk konfigurasi produksi.
- **Autentikasi:** Django Authentication dan `django-allauth` untuk Google OAuth.
- **Gambar:** Pillow dan media storage Django untuk foto profil serta produk.
- **Deployment:** PWS dengan GitHub Actions.

## Menjalankan Proyek secara Lokal

Jalankan perintah berikut dari folder repository. Contoh menggunakan PowerShell di Windows:

```powershell
python -m venv env
.\env\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Jika `.env` sudah ada, gunakan konfigurasi yang ada tanpa menimpanya. Isi variabel yang diperlukan pada `.env`, lalu jalankan:

```powershell
$env:PRODUCTION='False'
.\env\Scripts\python.exe manage.py migrate
.\env\Scripts\python.exe manage.py runserver
```

Buka `http://127.0.0.1:8000/` untuk mengakses aplikasi. Akun dapat dibuat melalui halaman registrasi. Untuk mengakses Django admin, buat superuser:

```powershell
.\env\Scripts\python.exe manage.py createsuperuser
```

### Konfigurasi Integrasi

- **Google login:** isi `GOOGLE_CLIENT_ID` dan `GOOGLE_CLIENT_SECRET` pada environment aplikasi. Daftarkan callback `/accounts/google/login/callback/` dengan domain dan protokol yang sesuai pada Google Cloud. Untuk lokal gunakan `ACCOUNT_DEFAULT_HTTP_PROTOCOL=http`; pada PWS gunakan HTTPS.
- **Email:** default console backend menampilkan email di terminal. Konfigurasikan SMTP melalui variabel pada `.env.example` untuk mengirim email ke inbox.
- **Media:** foto profil dan produk menggunakan media storage Django. Server deployment perlu menyediakan penyimpanan persisten dan akses URL media agar file tidak hilang saat redeploy.
- **Rahasia aplikasi:** `.env` lokal tidak ikut dipush ke GitHub. Environment aplikasi PWS dikonfigurasi terpisah dari secret GitHub Actions yang digunakan untuk deploy.

### Data Demo

Command berikut bersifat opsional untuk pengembangan lokal. Gunakan akun demo yang sudah dibuat:

```powershell
.\env\Scripts\python.exe manage.py seed_products --username <username-akun-demo>
.\env\Scripts\python.exe manage.py seed_account_demo --username <username-akun-demo>
```

Data demo membantu memeriksa tampilan katalog dan halaman akun. Data tersebut bukan transaksi, pembayaran, atau review nyata.

## Pengujian

Jalankan pemeriksaan Django dan seluruh tes proyek:

```powershell
$env:PRODUCTION='False'
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py test
```

Untuk menguji app tertentu, tambahkan nama app, misalnya `python manage.py test accounts` atau `python manage.py test products`. Konfigurasi coverage yang tersedia saat ini mengukur app `accounts`, bukan seluruh MVP:

```powershell
.\env\Scripts\python.exe -m coverage run manage.py test accounts
.\env\Scripts\python.exe -m coverage report
```
