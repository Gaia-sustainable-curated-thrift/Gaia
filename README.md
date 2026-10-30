# Gaia

**Gaia** adalah platform marketplace thrifting untuk membeli dan menjual pakaian bekas layak pakai. Melalui konsep **circular fashion**, Gaia ingin memberikan pakaian kesempatan kedua sekaligus mengurangi limbah *fast fashion*.

| Informasi | Keterangan |
| --- | --- |
| **Aplikasi (deployed)** | https://danar-iqbal-gaia.pws.cs.ui.ac.id |
| **Desain** | [Gaia di Figma](https://www.figma.com/design/gTTsLkfL1qaaPdEomnRfKf/Gaia?node-id=1-4&t=S3z03qUIKvsz1lNL-1) |
| **Deployment** | PWS, otomatis lewat GitHub Actions setelah semua test lulus |

## Daftar Isi

- [Fokus MVP](#fokus-pengembangan-mvp) dan [pembagian modul](#cakupan-mvp-dan-pembagian-modul)
- Modul: [User](#modul-user--authentication-danar), [Product](#modul-product-kayla), [Chat](#modul-chat-deva), [Transaksi](#modul-transaksi-salma), [Review & Rating](#modul-review--rating-keisha)
- [API dan integrasi](#api-dan-integrasi-mvp)
- [Menjalankan proyek lokal](#menjalankan-proyek-secara-lokal)
- [Pengujian](#pengujian)
- [Deployment PWS](#auto-deploy-ke-pws) dan [keamanan](#keamanan-dan-konfigurasi-deployment)
- [Pengembangan setelah MVP](#pengembangan-setelah-mvp)
- [AI disclosure](#pernyataan-penggunaan-ai-ai-disclosure)

## Fokus Pengembangan: MVP

**Saat ini, tim Gaia sedang mengembangkan Minimum Viable Product (MVP) yang terdiri dari lima modul utama: User, Product, Chat, Transaksi, serta Review & Rating.** Pengembangan tahap ini memprioritaskan penyelesaian dan integrasi kelima modul agar alur dasar marketplace dapat digunakan dari pendaftaran akun hingga pemberian review setelah transaksi.

Pembagian tanggung jawab MVP adalah **Danar: User, Kayla: Product, Deva: Chat, Salma: Transaksi, dan Keisha: Review & Rating**. Cakupan tiap modul dijelaskan pada bagian pembagian modul di bawah.

**Fitur selain kelima modul tersebut berada di luar cakupan pengembangan MVP.** Pengembangan fitur tambahan baru dilakukan setelah seluruh modul MVP selesai dikembangkan, terintegrasi, diuji, dan berjalan dengan baik. Fitur tambahan yang sudah terdapat pada kode tetap dapat dipertahankan, tetapi bukan prioritas penyelesaian tahap MVP.

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

Pencarian/filter dasar menjadi bagian pendukung Product, dan keranjang menjadi bagian Transaksi. Keduanya tidak memiliki penanggung jawab modul terpisah. Wishlist dasar menjadi bagian modul User. Halaman My Products (Produk Saya) di area akun menampilkan listing milik pengguna dan menghubungkan aksi jual, edit, serta hapus dari modul Product. Semua pengguna terdaftar dapat menjadi seller tanpa pendaftaran peran tambahan. Kelima modul dikembangkan dengan pembatasan akses sesuai peran dan kepemilikan data.

## User Roles dalam MVP

| Role | Peran dan target hak akses |
| ---- | ------------------------- |
| **Guest** | Melihat katalog, mencari produk, dan melihat detail produk; registrasi/login untuk menggunakan fitur akun. |
| **Registered User** | Dapat berperan sebagai buyer dan seller: mengelola profil/listing sendiri, menyimpan produk ke wishlist, berkomunikasi, bertransaksi, serta memberikan review/rating sesuai ketentuan transaksi. |
| **Admin** | Mengelola data melalui Django admin dan memverifikasi pembayaran/pengiriman melalui Manage Orders. Dashboard dan moderasi lanjutan bukan bagian target MVP saat ini. |

## Tampilan Aplikasi

| Beranda (desktop) | Beranda (mobile) |
| :---: | :---: |
| ![Beranda desktop](docs/screenshots/home-desktop.jpg) | ![Beranda mobile](docs/screenshots/home-mobile.jpg) |

| Halaman listing | Search dengan filter |
| :---: | :---: |
| ![Listing](docs/screenshots/listing.jpg) | ![Search dan filter](docs/screenshots/search-filter.jpg) |

| Detail produk (pembeli) | Shopping bag |
| :---: | :---: |
| ![Detail produk](docs/screenshots/product-detail.jpg) | ![Shopping bag](docs/screenshots/bag-drawer.jpg) |

| Detail produk (pemilik listing) | Form jual / edit |
| :---: | :---: |
| ![Detail untuk pemilik](docs/screenshots/product-owner.jpg) | ![Form jual](docs/screenshots/sell-form.jpg) |

| Card produk milik sendiri di mobile |
| :---: |
| ![Card pemilik di mobile](docs/screenshots/cards-owner-mobile.jpg) |

## Sumber Data (Dataset)

Katalog Gaia tidak diambil dari dataset publik atau API katalog eksternal. Data pengembangan berasal dari listing yang dibuat tim dan fixture demo:

- **Katalog dasar:** `seed_products` menambahkan 4 produk contoh dan 10 kategori (Women/Men beserta Tops, Bottoms, Shoes, dan Bags).
- **Katalog thrift tambahan:** `seed_thrift_catalog` menambahkan 10 listing sintetis dengan aset ilustrasi yang sudah ada di repository. Command dapat diulang tanpa menggandakan listing yang sama untuk seller yang sama.
- **Akun:** dibuat melalui registrasi atau login Google. `seed_account_demo` menambahkan snapshot order dan wishlist ke akun demo yang sudah ada; command ini tidak membuat kredensial akun.
- **Review demo:** `seed_reviews` membuat review sintetis untuk kebutuhan pengujian tampilan.

Data demo bukan penawaran barang, pembayaran, transaksi, atau review nyata. Google OAuth dan Cloudinary merupakan integrasi autentikasi/penyimpanan, bukan sumber dataset katalog.

## Modul User / Authentication (Danar)

Modul User menyediakan identitas akun dan area pribadi yang digunakan bersama oleh modul Product, Chat, Transaksi, serta Review & Rating. Autentikasi menggunakan Django Authentication; Google login menggunakan `django-allauth`.

### Fitur

- **Registrasi dan autentikasi:** membuat akun dengan nama lengkap, email, dan password; login menggunakan email atau username; login Google; serta logout melalui POST dengan konfirmasi.
- **Profil:** melihat dan mengubah nama, username, nomor telepon, kota, negara, serta foto profil. Nama, username, nomor telepon, kota, dan negara wajib diisi saat menyimpan perubahan profil; foto profil opsional. Email tidak dapat diubah melalui form profil. Foto JPG/PNG/WebP dibatasi 2 MB dan dimensi 4096 piksel per sisi, lalu diproses menjadi gambar persegi 512 x 512 piksel.
- **Keamanan akun:** verifikasi email dengan tautan 24 jam dan kirim ulang dengan cooldown satu menit per akun; ganti password untuk akun dengan password lokal; serta reset password melalui email. Akun tanpa password lokal mendapat keterangan mengenai external sign-in.
- **Penghapusan akun:** konfirmasi password untuk akun lokal atau tautan email untuk akun tanpa password lokal, disertai frasa `DELETE` dan persetujuan penghapusan. Akun dengan pesanan pembelian atau penjualan yang belum selesai tidak dapat dihapus.
- **Wishlist:** melihat produk favorit, menghapus item dengan soft delete, dan mengembalikan penghapusan terakhir melalui undo. Produk berstatus sold disembunyikan dari daftar favorit yang ditampilkan.
- **Area akun:** ringkasan aktivitas, My Products dengan filter available/sold, serta daftar dan detail My Orders. My Products, My Orders, dan Wishlist menggunakan pagination 12 item per halaman.

### Hak akses dan batas integrasi

| Aksi | Guest | Pengguna login |
| ---- | ----- | -------------- |
| Registrasi, login, permintaan reset password | tersedia | registrasi/login mengarahkan ke profil |
| Melihat atau mengubah profil | diarahkan ke login | hanya akun sendiri |
| Melihat wishlist | diarahkan ke login | hanya data milik sendiri |
| Melihat pesanan | diarahkan ke login | pesanan sendiri; staff aktif dapat mengakses Manage Orders |
| Menghapus/mengembalikan item wishlist | tidak | hanya item sendiri, melalui POST |
| Melihat My Products | diarahkan ke login | hanya listing sendiri |
| Menghapus akun | tidak | akun sendiri setelah konfirmasi dan pemeriksaan pesanan |

View membatasi akses berdasarkan pengguna login, dan form perubahan data menggunakan CSRF. Keunikan email nonkosong dijamin pada database; username support dicadangkan untuk akun sistem. Status verifikasi email bersumber dari `allauth.account.EmailAddress`.

Halaman akun menjadi pintu masuk ke modul lain: aksi buat/edit/hapus listing ditangani Product, sedangkan checkout, pembayaran, pembatalan, dan perubahan status transaksi menjadi tanggung jawab modul Transaksi. `AccountOrder` saat ini berada di app `accounts` dan digunakan bersama oleh Transaksi, Chat, serta Review & Rating. Menampilkan order di halaman akun tidak berarti modul User memverifikasi pembayaran.

### Peta kode

| File | Isi |
| ---- | --- |
| `accounts/models.py` | profil tambahan, snapshot wishlist, dan model pesanan bersama |
| `accounts/forms.py` | form login, registrasi, edit profil/foto, dan konfirmasi hapus akun |
| `accounts/views.py`, `accounts/urls.py`, `accounts/order_display.py` | alur akun, verifikasi, wishlist, My Products, serta tampilan status My Orders |
| `accounts/adapters.py`, `accounts/identity.py` | penyesuaian allauth dan pemeriksaan username sistem |
| `accounts/avatars.py`, `accounts/signals.py` | penamaan foto dan pembersihan avatar setelah commit |
| `accounts/migrations/` | skema akun, integritas email, dan pemindahan status verifikasi lama |
| `accounts/management/commands/` | audit email duplikat dan data demo akun |
| `templates/accounts/`, `templates/registration/` | halaman akun, autentikasi, serta template email |
| `static/js/accounts.js`, `static/css/accounts.css` | interaksi dan styling area akun |
| `accounts/tests.py` | unit test dan pengujian request untuk alur akun serta pembatasan akses |

### Rute

Semua rute berikut menggunakan awalan `/accounts/`.

| URL | Fungsi |
| --- | ------ |
| `register/`, `created/`, `login/`, `logout/` | registrasi, konfirmasi akun, login, dan logout |
| `google/login/` | masuk melalui Google; callback di `google/login/callback/` |
| `verify/<token>/`, `verify/resend/` | verifikasi dan kirim ulang email |
| `profile/`, `profile/edit/`, `settings/` | profil dan pengaturan akun |
| `password/change/`, `password/reset/` | ganti password dan awal alur reset melalui email |
| `products/` | My Products |
| `orders/`, `orders/<pk>/` | daftar dan detail pesanan sendiri |
| `orders/?scope=manage` | daftar pesanan untuk staff aktif yang memverifikasi pembayaran dan pengiriman |
| `wishlist/`, `wishlist/<pk>/remove/`, `wishlist/undo/` | daftar favorit, hapus, dan undo |
| `delete/`, `delete/email/`, `delete/confirm/<token>/` | konfirmasi penghapusan akun |

## Modul Product (Kayla)

### Fitur

- **Katalog:** beranda, halaman per departemen (Women/Men), halaman "Picked For You", tab kategori yang menyaring card tanpa reload.
- **Search dan filter:** cari berdasarkan judul, deskripsi, tag, atau kategori; filter harga, gender, kategori, dan kondisi. Filter memakai **HTMX**, jadi hasil dan jumlahnya berganti tanpa reload dan URL tetap bisa dibagikan.
- **Detail produk:** galeri foto dengan zoom, info seller beserta rating dari review, dan rekomendasi "Also see".
- **CRUD listing (hanya pemilik):** buat, edit, dan hapus listing dengan validasi ketat (harga rupiah, maksimal 5 foto, ukuran dan isi gambar diperiksa). Form dikirim lewat `fetch`, error validasi muncul langsung di form. Hapus dari card langsung menghilangkan card tanpa reload. Listing yang sudah **sold** disembunyikan dari toko tetapi tetap bisa dibuka pemiliknya.
- **Shopping bag:** disimpan di session sehingga tamu juga bisa belanja. Tombol "Add to bag" dan "Save to wishlist" memakai **optimistic UI**: tampilan berubah seketika, lalu dibatalkan otomatis kalau server menolak. Ditekan lagi berarti membatalkan (undo).
- **Microinteraction:** foto produk "terbang" ke bag, ledakan hati kecil di wishlist, transisi foto dari card ke halaman detail, tab yang bergeser, drawer yang meluncur, navbar yang menyembunyikan diri saat scroll. Semua mati otomatis kalau pengguna mengaktifkan *reduce motion*.

### Hak akses dan keamanan

| Aksi | Guest | Registered User | Pemilik listing |
| ---- | :---: | :---: | :---: |
| Lihat katalog, search, detail | ya | ya | ya |
| Add to bag | ya | ya | tidak (tidak bisa beli produk sendiri) |
| Wishlist | diarahkan ke login | ya | tidak |
| Buat listing | diarahkan ke login | ya | ya |
| Edit atau hapus listing | tidak | tidak (404) | ya |
| Buka listing yang sudah sold | tidak (404) | tidak (404) | ya |

- **`@owner_required`** (`products/decorators.py`): mengambil listing dari slug URL hanya kalau milik user yang login. Selain itu 404, bukan 403, supaya listing orang lain tidak bisa ditebak.
- **`@rate_limit`** (`products/decorators.py`): membatasi jumlah POST per user (tamu per sesi). Contoh: bikin listing 10 per jam, bag 60 per menit. Kalau terlampaui, server menjawab 429 dengan header `Retry-After` dan pesan yang ditampilkan di halaman.
- Seller, slug, dan status tidak ada di form, jadi tidak bisa diubah dengan memanipulasi request. Parameter `?next=` hanya diterima kalau mengarah ke situs ini.

### Peta kode

| File | Isi |
| ---- | --- |
| `products/models.py` | `Category`, `Product`, `ProductImage` |
| `products/forms.py` | form listing, field harga rupiah, validasi foto |
| `products/views.py` | halaman toko, jual/edit/hapus, bag, wishlist (urut sesuai alur pengunjung) |
| `products/decorators.py` | `owner_required` dan `rate_limit` |
| `products/cart.py` | logika shopping bag di session |
| `products/storage.py` | memilih tempat simpan foto (lokal atau Cloudinary) |
| `templates/products/` | halaman dan potongan template (`includes/`) |
| `static/js/gaia.js` | inti JS: search navbar, bag, toast, navbar |
| `static/js/products/` | satu file JS per fitur: tabs, search, gallery, wishlist, listing-form, listing-delete, home, page-transitions |
| `products/tests.py`, `test_*.py`, `e2e.py` | unit test dan functional test Playwright |

### Rute

| URL | Fungsi |
| --- | ------ |
| `/products/`, `/products/shop/<gender>/`, `/products/picked/` | beranda dan listing; `gender` bernilai `women` atau `men` |
| `/products/search/?q=` | search dan filter |
| `/products/<slug>/` | detail produk |
| `/products/sell/`, `/products/<slug>/edit/`, `/products/<slug>/delete/` | jual, edit, hapus (login, hanya pemilik) |
| `/products/bag/add/<slug>/`, `bag/remove/<slug>/`, `bag/set/<slug>/`, `bag/undo/` | shopping bag |
| `/products/wishlist/add/<slug>/`, `wishlist/remove/<slug>/` | wishlist |

## Modul Chat (Deva)

- Inbox dan ruang percakapan untuk buyer?seller, bantuan Gaia Care, serta pertanyaan terkait pesanan.
- Pesan teks, gambar, berbagi produk, penawaran harga, status baca, dan penghitung pesan belum dibaca. Penawaran dapat diterima/ditolak oleh seller; harga hasil penawaran belum diterapkan otomatis pada checkout.
- Akses percakapan dibatasi ke peserta. Akun support harus merupakan akun staff aktif yang dipercaya aplikasi.
- Pembaruan percakapan menggunakan polling endpoint JSON internal, bukan Django Channels/WebSocket.

Kode utama berada di `chat/models.py`, `chat/services.py`, `chat/views.py`, serta template dan JavaScript chat. Rute utamanya `/chat/`, `/chat/<pk>/`, `/chat/support/`, `/chat/order/<order_id>/`, dan `/chat/api/...`.

## Modul Transaksi (Salma)

- Checkout dari shopping bag: alamat penerima, metode pembayaran, konfirmasi pesanan, dan reservasi produk selama 15 menit.
- Satu listing thrift mewakili satu barang. Reservasi mencegah checkout ganda pada barang yang sama; pesanan batal/kedaluwarsa melepas reservasi yang masih terkait dengan pesanan tersebut.
- Status transaksi mencakup active/awaiting payment, paid, in transit, completed, cancelled, dan expired. Riwayat pesanan tetap tersedia setelah pembatalan.
- Pembayaran diverifikasi manual oleh staff aktif. Buyer dapat membatalkan pesanan yang belum terverifikasi dan mengonfirmasi penerimaan setelah barang dikirim. Seluruh aksi perubahan status menggunakan POST dan CSRF.

Kode utama berada di `transaction/models.py`, `transaction/forms.py`, `transaction/views.py`, dan `transaction/urls.py`. Model pesanan bersama `AccountOrder` berada di `accounts/models.py`.

| Rute | Fungsi |
| --- | --- |
| `/transaction/checkout/`, `shipping/`, `payment/`, `confirmation/` | alur checkout dan ringkasan pesanan |
| `/transaction/orders/<order_id>/cancel/` | pembatalan oleh pemilik pesanan |
| `/transaction/orders/<order_id>/confirm-payment/` | verifikasi pembayaran oleh staff aktif |
| `/transaction/orders/<order_id>/ship/` | staff mengisi kurir/resi dan menandai pengiriman |
| `/transaction/orders/<order_id>/complete/` | buyer mengonfirmasi barang diterima |

### Integrasi My Orders

My Orders membaca `TransactionOrderState` dari modul Transaksi agar status Paid, Cancelled, dan Expired tidak ditampilkan sebagai Awaiting payment. Buyer bisa membatalkan pesanan yang belum terverifikasi, lalu mengonfirmasi penerimaan setelah barang dikirim. Konfirmasi pembayaran hanya tersedia bagi akun staff aktif melalui Orders > Manage Orders; buyer tidak dapat menandai dirinya sudah lunas. Staff mengisi kurir dan nomor resi sebelum menandai pengiriman. Pembayaran belum terhubung ke gateway otomatis.

Aksi memakai endpoint POST milik `transaction` dan kembali ke detail pesanan. Reservasi pesanan batal/kedaluwarsa dilepas hanya jika masih milik pesanan tersebut. Riwayat tetap terlihat, dan pesanan cancelled/expired tidak memblokir penghapusan akun. Snapshot lama tanpa state transaksi tetap dapat dibaca. Integrasi ini memerlukan migrasi app `transaction` sampai `0003_sync_order_state_choices`.

## Modul Review & Rating (Keisha)

- Review dan rating seller dikaitkan dengan pesanan yang sudah completed. Aksi memberi review tersedia dari detail My Orders ketika pengguna memenuhi syarat.
- Pengguna dapat melihat ringkasan rating seller dan menyaring review berdasarkan bintang. Pemilik review dapat mengedit atau menghapus review miliknya.
- Fitur pendukung meliputi penandaan helpful, balasan seller, dan pelaporan review dengan pemeriksaan akses pada backend.

Kode utama berada di `reviews/models.py`, `reviews/forms.py`, `reviews/views.py`, dan template tag pada `reviews/templatetags/`. Rute utama meliputi `/reviews/account/`, `/reviews/seller/<seller_id>/`, serta `/reviews/order/<order_id>/create/`.

## API dan Integrasi MVP

Tabel berikut mencatat integrasi yang tersedia pada kode MVP. Nilai environment menentukan apakah layanan tersebut aktif pada suatu deployment.

| API / teknologi | Status di kode saat ini | Pemakaian / tindak lanjut |
| --------------- | ----------------------- | ------------------------ |
| **Google OAuth 2.0 melalui `django-allauth`** | **Sudah terintegrasi** pada modul User. | Login Google menggunakan client ID/secret dari environment dan callback `/accounts/google/login/callback/`. Operasionalnya memerlukan konfigurasi Google Cloud dan PWS. |
| **Cloudinary (penyimpanan foto produk)** | **Kode tersedia**, aktif kalau variabel `CLOUDINARY_URL` diisi. Tanpa itu foto disimpan di folder `media/` seperti biasa. | Foto produk disimpan di Cloudinary supaya tidak hilang saat PWS membangun ulang aplikasi. Foto chat tetap di server agar privat. Ini layanan penyimpanan, bukan sumber data. |
| **Email Django / SMTP** | **Alur email tersedia**, default masih console backend. Ini mekanisme pengiriman email, bukan public API yang sudah terhubung ke vendor tertentu. | Email verifikasi/reset dicetak di terminal pada konfigurasi default. SMTP harus dikonfigurasi agar email benar-benar dikirim ke inbox. |

Endpoint JSON chat dan aksi aplikasi merupakan API internal. Pembayaran saat ini menggunakan verifikasi manual; belum ada integrasi gateway pembayaran, callback/webhook, atau mock payment API. Data seed dan snapshot demo bukan bukti keberhasilan integrasi layanan eksternal.

## Teknologi

- **Backend:** Python dan Django (arsitektur MTV).
- **Frontend:** Django Templates, HTML, CSS, JavaScript (dipecah per fitur), dan **HTMX** untuk filter search.
- **Database:** SQLite untuk pengembangan lokal dan PostgreSQL untuk konfigurasi produksi.
- **Autentikasi:** Django Authentication dan `django-allauth` untuk Google OAuth.
- **Gambar:** Pillow, media storage Django, dan Cloudinary (opsional) untuk foto produk.
- **Pengujian:** Django test, `coverage`, dan Playwright untuk functional test di browser.
- **Deployment:** PWS dengan GitHub Actions (test lebih dulu, baru deploy).

## Menjalankan Proyek secara Lokal

Jalankan perintah berikut dari folder repository.

**Windows (PowerShell):**

```powershell
python -m venv env
.\env\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Jika `.env` sudah ada, gunakan konfigurasi yang ada tanpa menimpanya. Isi variabel yang diperlukan pada `.env` (terutama `SECRET_KEY`, supaya sesi login tidak hilang setiap server restart), lalu jalankan:

```powershell
$env:PRODUCTION='False'
.\env\Scripts\python.exe manage.py migrate
.\env\Scripts\python.exe manage.py runserver
```

**macOS / Linux:**

```bash
python3 -m venv env && source env/bin/activate
pip install -r requirements-dev.txt
cp -n .env.example .env
python manage.py migrate
python manage.py runserver
```

Buka `http://127.0.0.1:8000/` untuk mengakses aplikasi. Akun dapat dibuat melalui halaman registrasi. Untuk mengakses Django admin, buat superuser dengan `python manage.py createsuperuser`.

### Konfigurasi Integrasi

- **Google login:** isi `GOOGLE_CLIENT_ID` dan `GOOGLE_CLIENT_SECRET` pada environment aplikasi. Daftarkan callback `/accounts/google/login/callback/` dengan domain dan protokol yang sesuai pada Google Cloud. Untuk lokal gunakan `ACCOUNT_DEFAULT_HTTP_PROTOCOL=http`; pada PWS gunakan HTTPS.
- **Email:** default console backend menampilkan email di terminal. Konfigurasikan SMTP melalui variabel pada `.env.example` untuk mengirim email ke inbox.
- **Foto produk (Cloudinary):** kosongkan `CLOUDINARY_URL` untuk menyimpan foto di folder `media/`. Di PWS, isi dengan nilai dari dashboard Cloudinary (`cloudinary://API_KEY:API_SECRET@CLOUD_NAME`) lewat environment aplikasi, jangan lewat repository. Foto yang diunggah sebelum variabel diisi tidak berpindah otomatis dan perlu diunggah ulang.
- **Media lain:** foto profil dan foto chat memakai media storage Django. Server deployment perlu menyediakan penyimpanan persisten dan akses URL media agar file tidak hilang saat redeploy.
- **Rahasia aplikasi:** `.env` lokal tidak ikut dipush ke GitHub. Environment aplikasi PWS dikonfigurasi terpisah dari secret GitHub Actions yang digunakan untuk deploy.

### Data Demo

Command berikut bersifat opsional untuk pengembangan lokal. Gunakan akun demo yang sudah dibuat:

```bash
python manage.py seed_products --username <username-akun-demo>
python manage.py seed_thrift_catalog --username <username-akun-demo>
python manage.py seed_account_demo --username <username-akun-demo>
python manage.py seed_reviews --username <username-akun-demo>
```

Data demo membantu memeriksa tampilan katalog dan halaman akun. Data tersebut bukan transaksi, pembayaran, atau review nyata.

### Katalog demo 100 produk

Jalankan `python manage.py seed_demo_products --username danariqbalabi` untuk membuat 100 listing sintetis bernomor. Command memakai ilustrasi proyek, memberi label data demo, dan dapat diulang tanpa menggandakan atau mengembalikan listing yang sudah dihapus. `--count` dapat diisi 1 sampai 100. Command 10 produk `seed_thrift_catalog` tetap tersedia.

Admin juga dapat membuka Django admin > Products > Add 100 Demo Products, memilih username seller aktif, lalu mengonfirmasi. Aksi hanya tersedia bagi staff yang memiliki izin menambah produk, kategori, dan foto, serta memerlukan POST dan CSRF. Pada rilis ini, migrasi `products.0007` mengisi 100 produk untuk akun aktif `danariqbalabi` bila akun tersebut sudah ada di database tujuan. Migrasi tidak membuat akun atau menghapus produk ketika dibalik. Gambar memakai storage produk yang dikonfigurasi; Cloudinary mempertahankannya antar-deploy.

## Pengujian

Jalankan pemeriksaan Django dan seluruh unit test proyek:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Untuk menguji satu app, tambahkan namanya, misalnya `python manage.py test products`. Untuk mengukur coverage modul Product secara terpisah:

```bash
python -m coverage run --branch --source=products --omit='products/test*.py,products/e2e.py,products/migrations/*' manage.py test products
python -m coverage report --show-missing
```

Konfigurasi `.coveragerc` bawaan repository hanya mengukur app `accounts`, jadi perintah di atas memakai opsi sendiri.

### Pengujian modul User

Jalankan tes modul User dan laporan coverage dari root repository:

```bash
python manage.py test accounts.tests --verbosity 2
python -m coverage run manage.py test accounts.tests
python -m coverage report --show-missing
python -m coverage html
```

Buka `htmlcov/index.html` untuk melihat baris dan cabang yang tercakup. Tes menggunakan database terpisah, email in-memory, dan mock pada integrasi tertentu. Skenarionya mencakup registrasi/login, validasi input, keunikan email, verifikasi dan kirim ulang email, profil/avatar, ganti/reset password, penghapusan akun, wishlist, My Products, pagination, CSRF, serta akses data antaruser. Persentase coverage harus dibaca dari hasil eksekusi terbaru; angka tersebut tidak membuktikan tampilan browser, Google OAuth, atau pengiriman SMTP nyata sudah diuji.

**Functional test (Playwright):** mensimulasikan pengguna di browser sungguhan, misalnya filter search lewat HTMX, add to bag, wishlist, edit dan hapus listing, serta tampilan di HP.

```bash
pip install -r reviews/requirements-dev.txt
python -m playwright install chromium
python manage.py test products.e2e reviews.e2e --noinput
```

Kalau Chrome atau Edge sudah terpasang, set `GAIA_TEST_BROWSER` ke lokasi file aplikasinya agar tidak perlu mengunduh Chromium.

## Alur Kerja Git

- **Branch per orang dan per fitur**, misalnya `feat/products` atau `feat/chat`; tidak ada yang commit langsung ke `main`.
- **Conventional commits:** `feat:`, `fix:`, `test:`, `ci:`, `refactor:`, `docs:`, dengan pesan yang menjelaskan perubahan.
- **Pull request ke `main`**, ditinjau teman satu tim sebelum di-merge. Konflik diselesaikan dengan merge `main` ke branch fitur dulu, lalu dites ulang.
- **GitHub Actions** menjalankan seluruh test pada setiap pull request; deploy ke PWS hanya berjalan kalau test lulus dan perubahan sudah masuk `main`.

## Auto deploy ke PWS

Workflow `.github/workflows/deploy.yml` terdiri dari tiga job:

1. **Run tests**: cek tidak ada migrasi yang tertinggal, jalankan seluruh unit test, dan tampilkan laporan coverage.
2. **Run browser tests**: jalankan functional test Playwright (`products.e2e`, `reviews.e2e`) di Chromium.
3. **Deploy Gaia to PWS**: berjalan hanya untuk push/merge ke `main`, dan hanya kalau dua job di atas lulus. Commit dikirim ke branch `master` PWS Gaia.

Dua job pertama juga berjalan di setiap pull request ke `main`. Deploy bisa dijalankan manual dari tab **Actions > Push to PWS > Run workflow**, dengan branch `main`.

Repository secret `PWS_URL` harus berisi URL Git PWS dengan kredensial proyek, dikelola melalui **Settings > Secrets and variables > Actions**. Jangan masukkan kredensial ke file repository. Workflow memakai `actions/checkout@v7`, mengambil seluruh riwayat Git untuk deploy, dan mengantre deployment agar tidak bertabrakan. Push tidak memakai force; riwayat PWS yang berbeda perlu disinkronkan sebelum deployment bisa lanjut.

Untuk merilis perubahan, push atau merge feature branch ke `main`, lalu cek hasil **Push to PWS** di tab Actions. Tidak perlu push PWS manual lagi. Build aplikasi tetap dijalankan oleh PWS setelah menerima push.

## Keamanan dan Konfigurasi Deployment

### Konfigurasi keamanan deployment

Set `PRODUCTION=True` dan `SECRET_KEY` acak baru (minimal 50 karakter) melalui environment PWS sebelum deploy. Key lama di riwayat repository harus dianggap bocor dan tidak digunakan kembali. Nilai secret tidak boleh dimasukkan ke GitHub atau log. Rotasi key membuat sesi/token lama tidak berlaku.

Mode produksi mematikan debug, mengaktifkan cookie secure, redirect HTTPS, dan HSTS. Proxy PWS harus meneruskan serta menimpa `X-Forwarded-Proto`; jangan mempercayai header langsung dari klien. Jalankan `python manage.py check --deploy` dengan konfigurasi produksi. PWS memakai endpoint `/media/` aplikasi untuk foto upload yang telah diverifikasi sebagai gambar, dengan tipe konten hasil deteksi dan `X-Content-Type-Options: nosniff`. File HTML/SVG dan path di luar folder gambar ditolak. Foto chat hanya dapat diakses peserta percakapan; jangan memintas pemeriksaan akses ini melalui proxy publik. Endpoint ini tetap bekerja dengan `DEBUG=False`. Penyimpanan media harus persisten antar-deploy.

Rujukan: [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

### Integritas email akun

Email akun nonkosong memiliki unique index `LOWER(TRIM(email))` di database (SQLite/PostgreSQL). Aturan ini berlaku untuk registrasi biasa, Google/allauth, admin, serta penulisan langsung ke model. Akun sistem boleh tidak memiliki email. Sebelum migrasi, jalankan `python manage.py audit_account_emails`; bila ada duplikat lama, selesaikan kepemilikannya dahulu. Migrasi berhenti tanpa menggabungkan atau menghapus akun secara otomatis.

### Verifikasi dan identitas akun

Status verifikasi email dibaca dari `allauth.account.EmailAddress` untuk email akun saat ini. Migrasi memindahkan flag verifikasi profil lama tanpa menggabungkan akun. Pengguna dapat meminta ulang tautan melalui Account Settings; tautan berlaku 24 jam dan permintaan dibatasi satu kali per menit per akun, termasuk ketika berpindah browser atau pengiriman gagal. Mode produksi membuat tautan HTTPS meskipun upstream PWS menggunakan HTTP.

Username `gaiacare` dan username support yang dikonfigurasi tidak dapat dipilih oleh pengguna biasa. `GAIA_CARE_USER_ID` dapat menunjuk akun staff aktif yang disiapkan administrator; benturan username dengan akun biasa ditolak, tanpa menaikkan hak akun tersebut. Percakapan support lama yang salah tujuan memerlukan pemeriksaan admin.

## Pengembangan Setelah MVP

Setelah User, Product, Chat, Transaksi, dan Review & Rating selesai serta terintegrasi dengan baik, tim dapat melanjutkan:

- Community / Social Feed dan interaksi sosial.
- Outfit Generator dan rekomendasi berbasis AI.
- Wishlist lanjutan dan notifikasi favorit; wishlist dasar sudah termasuk dalam modul User pada MVP.
- Dashboard khusus, statistik, moderasi, dan pelaporan lanjutan.
- Peta/autocomplete alamat, Lemari pribadi, serta fitur pencarian, nego, dan notifikasi lanjutan di luar kebutuhan dasar MVP.
- Gateway pembayaran otomatis dan teknologi komunikasi real-time tambahan bila dibutuhkan.
- Penyimpanan cloud/persisten untuk jenis media yang belum menggunakannya, sesuai kebutuhan operasional.

Fitur-fitur tersebut bukan komitmen deliverable MVP dan tidak menjadi fokus pembagian tugas tahap pertama.

---

## Pernyataan Penggunaan AI (AI Disclosure)

Tim menggunakan AI sebagai asisten pemrograman dan mencatat penggunaannya secara terbuka. Bantuan mencakup penulisan kode, pengujian, dokumentasi, dan operasi pengembangan sesuai instruksi anggota tim. Penentuan kebutuhan, peninjauan hasil, serta tanggung jawab atas perubahan tetap berada pada pengembang masing-masing modul.

### Alat dan cakupan bantuan

| Alat | Dipakai oleh | Untuk apa |
| --- | --- | --- |
| **Claude Code** (asisten pemrograman dari Anthropic, dijalankan dari terminal/aplikasi desktop) | Kayla, modul Product | Menulis dan merapikan kode, menulis test, menambah animasi, menyusun CI, mereview kode, dan menjelaskan kode. |
| **OpenAI Codex / ChatGPT** | Danar, modul User / Authentication | Membantu memahami Django dan pembagian modul, menganalisis desain, menyusun dan meninjau implementasi akun, pengujian, integrasi, serta dokumentasi. |

### Bantuan AI untuk Product (Kayla)

Catatan penggunaan Claude Code mencakup penulisan dan perapian kode, penulisan test, penambahan animasi, penyusunan CI, review kode, serta penjelasan kode. Rincian strategi prompt, keterbatasan, dan pekerjaan manual modul Product belum diisi pada catatan sumber.

### Bantuan AI untuk User (Danar)

- Membaca referensi Gaia User dan Gaia Design System, memetakan alur akun, serta menjelaskan penerapannya pada Django Templates, CSS, dan JavaScript.
- Membantu pengembangan dan peninjauan form, view, model, template, serta pengujian untuk registrasi/login, profil dan avatar, verifikasi email, keamanan dan penghapusan akun, wishlist, My Products, serta tampilan My Orders.
- Membantu audit akses berdasarkan kepemilikan, validasi input, email duplikat, akun Google tanpa password lokal, tautan email di belakang proxy PWS, dan ketergantungan antar-modul.
- Menjelaskan unit test dan coverage, menjalankan pemeriksaan lokal, membantu operasi Git yang diminta, serta merapikan dokumentasi modul User.

Rekaman percakapan yang disertakan oleh pengembang: [Percakapan Codex/ChatGPT untuk modul User](https://chatgpt.com/s/cx_6ae4a2e5c8bc81918c1238f575ae4137).

### Strategi prompt

Untuk modul User, konteks diberikan berupa file proyek, referensi desain, materi tutorial, dan kebutuhan fitur. Permintaan dilakukan bertahap: membaca dan menganalisis terlebih dahulu, menjelaskan pilihan implementasi, lalu melakukan pekerjaan yang diminta. Audit dipersempit ke modul User saat diperlukan, dan temuan dibedakan antara tanggung jawab akun dengan integrasi Product, Transaksi, Chat, serta Review & Rating.

### Keterbatasan AI yang ditemui

Pada modul User, saran awal AI perlu dicocokkan dengan versi kode terbaru dan pembagian tugas tim. Contohnya, audit sempat mencampur kekurangan akun dengan alur transaksi yang merupakan tanggung jawab modul lain. Coverage 100% juga tidak menjamin semua perilaku benar: audit lanjutan menemukan kasus khusus pada registrasi bersamaan, verifikasi email, akun Google, dan penghapusan akun dengan penjualan aktif. Hasil tes lokal tidak menjadi bukti bahwa konfigurasi OAuth/SMTP di PWS atau seluruh tampilan browser telah berfungsi.

### Peran pengembang dan pemeriksaan hasil

Untuk modul User, Danar menentukan kebutuhan, memberikan referensi dan konteks, membahas kelayakan serta pembagian fitur, dan mengoordinasikan integrasi dengan anggota tim. Percakapan juga mencakup peninjauan hasil coverage yang dijalankan pengembang. Bantuan AI mencakup kode dan dokumentasi; tidak seluruh implementasi diklaim ditulis manual. Pemeriksaan akhir terhadap perubahan, kesesuaian dengan tugas, dan perilaku aplikasi tetap menjadi tanggung jawab pengembang modul.

<!-- Anggota lain dapat menambahkan disclosure berdasarkan penggunaan AI yang benar-benar dilakukan pada modul masing-masing. -->

---

**Gaia — A circular fashion marketplace where every piece gets a second chance.**

### Foto katalog contoh

Migrasi `products.0008` memperbarui 100 listing contoh milik `danariqbalabi` dengan nama barang tanpa awalan nomor dan 100 foto referensi berbeda sesuai kategori. ID/slug, status penjualan, dan riwayat pesanan tetap dipertahankan. Sumber metadata/foto tercatat di `static/images/demo-catalog/SOURCES.md` dan `products/demo_catalog_photos.json`; hak gambar tetap pada pemiliknya. Ini data demonstrasi, bukan barang nyata yang dijual. Tombol admin memakai foto terbaru; CLI dapat memakai `--natural-photos`.
