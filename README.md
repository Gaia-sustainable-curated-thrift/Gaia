# Gaia

**Gaia** adalah platform marketplace thrifting yang memungkinkan pengguna untuk membeli dan menjual pakaian bekas layak pakai dalam satu ekosistem yang terpercaya.

Mengusung konsep **circular fashion**, Gaia bertujuan untuk mengurangi limbah *fast fashion* dengan memberikan pakaian kesempatan kedua untuk dipakai dan dicintai kembali oleh pemilik baru.

Selain fitur jual-beli seperti checkout, offer, chat, wishlist, dan rating, Gaia memiliki fitur **Outfit Generator** yang membantu pengguna memadupadankan pakaian berdasarkan style, occasion, dan budget.

Gaia juga menyediakan fitur **Community** sebagai ruang bagi pengguna untuk berbagi outfit, thrift finds, tips fashion, serta berinteraksi dengan pengguna lain.

---

## Anggota Kelompok
| No. | Nama                | NPM          |
| --: | ------------------- | ------------ |
|   1 | **Danar Iqbal Abi Zaidan Suharso** | `2506534371` |
|   2 | **I Gede Devadatta A.D**            | `2506622481` |
|   3 | **Keisha Janice Maulina Napitupulu**          | `2506551232` |
|   4 | **Kayla Kirana Ali Trimardhany**           | `2506603854` |
|   5 | **Salma Maharani**           | `2506586532` |


## User Roles

| Role                | Deskripsi                                                                    | Hak Akses                                                                                                   |
| ------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **Guest**           | Pengguna yang belum login                                                    | Browse dan search listing, melihat detail produk, profil seller, dan Community                              |
| **Registered User** | Pengguna yang sudah terdaftar dan dapat berperan sebagai buyer maupun seller | Membeli, menjual, offer, chat, wishlist, rating, Outfit Generator, membuat dan berinteraksi dengan Community |
| **Admin**           | Pengelola dan moderator platform                                             | Moderasi listing, mengelola user, menangani laporan, mengelola Community, serta melihat statistik platform  |

---

## Rencana Modul

Gaia terdiri dari 10 modul utama:

| No. | Modul                         | Deskripsi                                                                                              |
| --: | ----------------------------- | ------------------------------------------------------------------------------------------------------ |
|   1 | **Users / Authentication**    | Register, login, logout, profile, alamat, public profile, dan Lemari pribadi                           |
|   2 | **Products / Listing**        | CRUD listing, kategori, ukuran, warna, brand, kondisi, style tag, status produk, dan upload multi-foto |
|   3 | **Search & Filter**           | Search produk, filter berdasarkan harga/ukuran/warna/kondisi/brand/style, dan sorting                  |
|   4 | **Wishlist / Favorite**       | Menyimpan produk favorit dan notifikasi terkait produk wishlist                                        |
|   5 | **Review & Rating**           | Rating dan review antara buyer dan seller setelah transaksi                                            |
|   6 | **Dashboard / Admin Panel**   | Dashboard user, administrasi user, moderasi listing, laporan, dan statistik platform                   |
|   7 | **Community / Social Feed**   | Post, feed, like, comment, reply, follow, repost, bookmark, hashtag, mention, dan report               |
|   8 | **Marketplace / Transaction** | Cart, checkout, nego, order, pembayaran, dan status transaksi                                          |
|   9 | **Chat / Messaging**          | Komunikasi buyer dan seller, conversation, real-time messaging, dan notifikasi                         |
|  10 | **Outfit Generator**          | Generate kombinasi outfit berdasarkan style, occasion, budget, serta opsi rekomendasi berbasis AI      |

---

## Public API / Mock API

| API / Technology                | Kegunaan                                                   | Modul                         |
| ------------------------------- | ---------------------------------------------------------- | ----------------------------- |
| **Cloudinary / AWS S3 API**     | Upload dan hosting foto produk serta foto Community        | Products / Listing, Community |
| **Midtrans / Xendit API**       | Pembayaran saat checkout                                   | Marketplace / Transaction     |
| **Django Channels / WebSocket** | Komunikasi real-time antara buyer dan seller               | Chat / Messaging              |
| **Anthropic Claude API**        | Rekomendasi outfit berdasarkan style, budget, dan occasion | Outfit Generator              |
| **Google Maps / Places API**    | Autocomplete dan pengelolaan alamat pengguna               | Users / Authentication        |


---

# Pembagian Modul Anggota

| No. | Anggota    | Modul 1                       | Modul 2                     | Fokus Tugas                                                                |
| --: | ---------- | ----------------------------- | --------------------------- | -------------------------------------------------------------------------- |
|   1 | **Salma**  | **Users / Authentication**    | **Wishlist / Favorite**     | Pengelolaan akun pengguna, autentikasi, profil, dan produk yang disimpan   |
|   2 | **Kayla**  | **Products / Listing**        | **Search & Filter**         | Pengelolaan listing produk serta pencarian dan penyaringan produk          |
|   3 | **Keisha** | **Review & Rating**           | **Chat / Messaging**        | Sistem reputasi pengguna dan komunikasi buyer–seller                       |
|   4 | **Deva**   | **Marketplace / Transaction** | **Dashboard / Admin Panel** | Proses transaksi, pembayaran, serta pengelolaan dashboard dan administrasi |
|   5 | **Danar**  | **Community / Social Feed**   | **Outfit Generator**        | Fitur social community dan sistem rekomendasi outfit                       |

---

**Gaia — A circular fashion marketplace where every piece gets a second chance.**

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

### Data demo dan integrasi modul

Akun baru tidak otomatis memiliki order atau wishlist. Untuk melihat state berisi data sesuai referensi, buat akun lokal khusus demo lalu jalankan:

```powershell
.\env\Scripts\python.exe manage.py seed_account_demo --username <username-akun-demo>
```

Username otomatis dari nama lengkap bisa dilihat pada halaman Profile. Command ini idempotent dan menambahkan tiga order serta satu wishlist ke akun yang dipilih tanpa membuat atau mengubah password. Foto contoh diekstrak dari PNG referensi yang diberikan.

`AccountOrder` adalah snapshot baca-saja untuk UI akun, dan `WishlistItem` menyimpan snapshot listing berdasarkan `product_key`. Keduanya perlu dihubungkan ke model Products/Marketplace ketika modul tersebut tersedia. UI tidak memproses pembayaran, checkout, atau menambah listing. Data sementara dapat dikelola lewat Django admin.

### Validasi

```powershell
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py test accounts
```

Tes mencakup akses halaman, login email, registrasi, verifikasi, simpan profil, pembatasan data antar pengguna, wishlist remove/undo, ganti/reset password, token sekali pakai, serta logout POST/CSRF. Layout memakai breakpoint desktop/tablet/mobile dan aset logo dari referensi. ZIP hanya menyertakan PNG; font memakai fallback lokal Georgia/Arial jika font desain tidak tersedia.
