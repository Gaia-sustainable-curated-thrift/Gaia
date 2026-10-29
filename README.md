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
| 1 | **Danar** | **User / Authentication** | Registrasi, login/logout, login Google, profil dan edit profil, verifikasi email, serta ganti/reset password. |
| 2 | **Kayla** | **Product / Listing** | Pengelolaan listing, foto produk, kategori, harga, kondisi, status ketersediaan, detail produk, serta pencarian/filter dasar untuk menemukan produk. |
| 3 | **Deva** | **Chat / Messaging** | Percakapan dan pesan antara buyer dan seller untuk membahas produk serta transaksi. |
| 4 | **Salma** | **Transaksi** | Keranjang, checkout, pembuatan pesanan, alur pembayaran, serta pelacakan status transaksi. |
| 5 | **Keisha** | **Review & Rating** | Pemberian dan penampilan review/rating setelah transaksi, dengan pembatasan berdasarkan pihak yang bertransaksi. |

Pencarian/filter dasar menjadi bagian pendukung Product, dan keranjang menjadi bagian Transaksi. Keduanya tidak memiliki penanggung jawab modul terpisah. Status implementasi dan integrasi masing-masing modul dijelaskan di bawah.

## User Roles dalam MVP

| Role | Peran dan target hak akses |
| ---- | ------------------------- |
| **Guest** | Melihat katalog, mencari produk, dan melihat detail produk; registrasi/login untuk menggunakan fitur akun. |
| **Registered User** | Dapat berperan sebagai buyer dan seller: mengelola profil/listing sendiri, berkomunikasi, bertransaksi, serta memberikan review/rating sesuai ketentuan transaksi. |
| **Admin** | Mengelola data melalui Django admin untuk mendukung operasional MVP. Dashboard dan moderasi lanjutan bukan bagian target MVP saat ini. |

## Status Implementasi Saat Ini

Status berikut berdasarkan source code pada checkout lokal saat README ini diperbarui (29 Oktober 2026). Ketersediaan di server tetap bergantung pada versi yang dideploy dan konfigurasi environment.

| Modul | Yang sudah tersedia | Yang masih perlu dikembangkan/diselesaikan |
| ----- | ------------------- | ----------------------------------------- |
| **User** | Registrasi, login/logout, profil/edit profil, verifikasi email bertoken, ganti/reset password, dan integrasi Google OAuth melalui `django-allauth`. | Pengiriman email ke inbox memerlukan SMTP; Google login memerlukan kredensial dan callback yang sesuai. Belum ada fitur hapus akun oleh pengguna. |
| **Product** | Katalog, detail, kategori, search/filter, pembuatan listing dan upload multi-foto lokal, serta status produk pada model. | Melengkapi alur edit/hapus listing pada UI dan integrasi antarmodul. |
| **Chat** | Belum ditemukan modul percakapan/pesan di checkout ini. | Model, endpoint, UI percakapan, otorisasi peserta, dan mekanisme pengiriman pesan. |
| **Transaksi** | Keranjang berbasis session serta tampilan daftar/detail snapshot pesanan (`AccountOrder`) pada halaman akun. | Checkout masih placeholder untuk pengguna yang login; pembuatan pesanan dari checkout, pembayaran, dan pembaruan status transaksi belum terintegrasi. |
| **Review & Rating** | Detail produk menampilkan nilai rating/jumlah review dari konstanta tampilan. | Model dan alur pemberian review/rating nyata, penyimpanan data, serta validasi kelayakan berdasarkan transaksi. |

Wishlist sudah tersedia sebagai fitur tambahan pada kode: penambahan dari produk, daftar favorit, hapus, dan undo. Keberadaannya tidak menjadikannya prioritas atau syarat penyelesaian MVP lima modul di atas.

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
- Wishlist lanjutan dan notifikasi favorit; implementasi dasar yang sudah ada tetap dipertahankan sebagai fitur tambahan.
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

## Menjalankan halaman User

```powershell
.\env\Scripts\python.exe manage.py migrate
.\env\Scripts\python.exe manage.py runserver
```

Buka `/accounts/register/` untuk membuat akun, atau `/accounts/login/` untuk login memakai email (username lama tetap didukung). Setelah login, pengguna masuk ke `/accounts/profile/`.

Halaman yang tersedia:

- `/accounts/profile/` dan `/accounts/profile/edit/`: profil, aktivitas, dan penyimpanan nama, username, telepon, kota, serta negara.
- `/accounts/orders/` dan `/accounts/orders/<id>/`: daftar/detail pesanan dengan status in transit, completed, atau awaiting payment.
- `/accounts/wishlist/`: favorit tersimpan, hapus, empty state, dan undo penghapusan terakhir.
- `/accounts/settings/` dan `/accounts/password/change/`: keamanan akun dan penggantian password tanpa mengakhiri sesi.
- `/accounts/password/reset/`: email reset, link bertoken, penggantian password, dan konfirmasi selesai.
- Logout menggunakan dialog konfirmasi dan POST dengan CSRF.

Registrasi mengirim link verifikasi email yang berlaku 24 jam. Status email hanya berubah setelah link valid dibuka; akun Google mengikuti status email terverifikasi dari allauth. Pengguna bisa melengkapi profil sambil menunggu verifikasi.

Untuk pengembangan, email verifikasi/reset dicetak di terminal runserver, bukan dikirim ke inbox. Untuk mengirim email sungguhan, isi konfigurasi SMTP di `.env` sesuai `.env.example`. Tombol Google tampil jika client ID dan secret sudah dikonfigurasi.

Google OAuth di PWS memakai callback `https://danar-iqbal-gaia.pws.cs.ui.ac.id/accounts/google/login/callback/`. Daftarkan URL ini persis, termasuk HTTPS dan slash terakhir, pada **Authorized redirect URIs** client OAuth di Google Cloud. `ACCOUNT_DEFAULT_HTTP_PROTOCOL` default-nya `https` agar callback tetap benar di belakang proxy PWS. Untuk runserver lokal, isi `ACCOUNT_DEFAULT_HTTP_PROTOCOL=http` di `.env` dan daftarkan callback localhost yang dipakai. Kredensial Google perlu tersedia di environment PWS; `.env` lokal tidak ikut deploy.

### Data demo dan integrasi modul

Akun baru tidak otomatis memiliki order atau wishlist. Untuk melihat state berisi data sesuai referensi, buat akun lokal khusus demo lalu jalankan:

```powershell
.\env\Scripts\python.exe manage.py seed_account_demo --username <username-akun-demo>
```

Username otomatis dari nama lengkap bisa dilihat pada halaman Profile. Command ini idempotent dan menambahkan tiga order serta satu wishlist ke akun yang dipilih tanpa membuat atau mengubah password. Foto contoh diekstrak dari PNG referensi yang diberikan.

`AccountOrder` masih merupakan snapshot baca-saja untuk UI akun dan belum dibuat otomatis dari checkout. `WishlistItem` sudah diisi dari modul Product berdasarkan `product_key`, tetapi tetap menyimpan snapshot informasi produk, bukan relasi ForeignKey langsung ke Product. Pembuatan listing tersedia pada modul Product; checkout/pembayaran terintegrasi belum tersedia. Data demo dapat dikelola lewat Django admin.

### Validasi

```powershell
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py test accounts
```

### Unit test dan coverage modul User

Suite pada `accounts/tests.py` mencakup tes lama dan tes tambahan modul User. Tes memakai database pengujian Django dan email in-memory, tanpa menghubungi SMTP atau Google secara langsung. Password hasher cepat hanya digunakan dalam tes, bukan pada konfigurasi aplikasi.

```powershell
.\env\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PRODUCTION='False'
.\env\Scripts\python.exe -m coverage run manage.py test accounts
.\env\Scripts\python.exe -m coverage report
.\env\Scripts\python.exe -m coverage html
```

Konfigurasi `.coveragerc` mengukur line dan branch coverage seluruh package `accounts`, termasuk form, view, model, context processor, template filter, dan command demo. File tes dan migration dikecualikan dari pengukuran. `coverage report` gagal jika coverage gabungan kurang dari 91%. Laporan HTML tersedia di `htmlcov/index.html`. Semua tes modul User dijalankan bersama melalui `python manage.py test accounts`.

Hasil pengukuran 29 Oktober 2026 di `C:\Coding\gaia` menggunakan `accounts.tests`: **60 tes lulus, line coverage 100% (269 statement) dan branch coverage 100% (26 cabang)**. Cakupan ini mengukur kode Python milik app `accounts`, bukan kode internal Django/allauth, HTML/CSS, atau keberhasilan integrasi Google/SMTP di server.

Tes mencakup akses halaman, login email, registrasi, verifikasi, simpan profil, pembatasan data antar pengguna, wishlist remove/undo, ganti/reset password, token sekali pakai, serta logout POST/CSRF. Layout memakai breakpoint desktop/tablet/mobile dan aset logo dari referensi. Font lokal tersedia pada aset statis, dengan fallback Georgia/Arial sesuai stylesheet.
