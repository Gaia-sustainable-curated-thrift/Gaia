# Catatan TDD Review & Rating

CRUD awal sudah dikerjakan sebelumnya dan dilindungi tes regresi.
Catatan ini tidak mengklaim seluruh kode awal dibuat dengan TDD.
Pada siklus berikut, tes gagal dijalankan sebelum kode diperbaiki.

## 1. Data demo yang dapat diulang

**Red:** `test_seed_is_repeatable_and_preserves_existing_review`
gagal karena command `seed_reviews` belum tersedia.

**Green:** command menggunakan `get_or_create` dalam transaksi.
Pemanggilan pertama membuat lima review, sedangkan pemanggilan
kedua membuat nol. Review awal tetap utuh.

**Refactor:** menambahkan validasi seller dan jumlah data,
serta pengujian jumlah default 50 review.

## 2. Melindungi akun pengguna yang sudah ada

**Red:** `test_seed_does_not_impersonate_an_existing_real_account`
gagal karena command menggunakan akun yang namanya cocok dengan
nama akun demo.

**Green:** command menolak akun yang sudah mempunyai password.

Tes tambahan untuk akun aktif tanpa password juga ditulis terlebih
dahulu dan gagal. Implementasi kemudian diperbaiki: akun demo baru
dibuat nonaktif, sedangkan akun aktif atau akun berpassword yang
sudah ada ditolak. Transaksi membatalkan perubahan saat terjadi benturan.

## 3. Feedback ketika AJAX gagal

**Red:** tes browser memutus request Helpful, tetapi pesan status
tetap tersembunyi.

**Green:** helper mencari area status halaman ketika form aksi
tidak memiliki area pesan sendiri. Pesan error ditampilkan dan
tombol kembali aktif.

## 4. Akses rating lewat keyboard

**Red:** setelah memilih rating 3 dan menekan ArrowRight, rating 4
tidak terpilih karena urutan radio dalam DOM terbalik.

**Green:** radio dikembalikan ke urutan 1–5. CSS `:has()` mengatur
highlight bintang tanpa membalik urutan DOM. Rating dapat dipilih
melalui klik maupun keyboard.

## 5. Integrasi navigasi review seller

**Red:** dari tiga tes menu akun, dua gagal karena menu Seller Reviews
belum dipasang. Tes tautan review seller pada halaman produk juga gagal.

**Green:** template akun memanggil `seller_reviews_nav`, sedangkan
template produk memanggil `seller_rating`. Keempat tes integrasi lulus.
Menu hanya muncul untuk seller dan aktif pada halaman review miliknya.
Rating produk menjadi tautan ke review akun seller.

## 6. Review berdasarkan pembelian selesai

**Red:** 19 tes tambahan dijalankan pada kode lama: satu gagal dan 18 error.
Pesanan belum mempunyai relasi produk/seller, review belum mempunyai relasi
pesanan, dan pengguna tanpa pembelian masih dapat membuka form.

**Green:** relasi nullable ditambahkan untuk mempertahankan data lama.
Checkout mengisi produk dan seller; form hanya menerima pesanan selesai milik
buyer untuk seller yang dituju. Pemeriksaan diulang dalam transaksi dengan
penguncian pesanan. OneToOneField membatasi satu review per pesanan.
Ke-19 tes tambahan kemudian lulus. Tes browser CRUD juga memastikan
review yang baru dibuat mempunyai badge Verified buyer.

Fixture tes CRUD lama diperbarui dengan pesanan selesai; tes lama tidak
mengabaikan atau melemahkan aturan pembelian. Data demo lama tetap tanpa
badge, bukan disamarkan sebagai pembelian sungguhan.

## 7. Tombol sesuai kelayakan review

**Red:** tujuh tes perilaku tombol ditambahkan; tiga gagal pada versi lama.
Tombol masih menawarkan review baru setelah semua pesanan diulas,
kepada buyer yang belum memenuhi syarat, dan pada respons filter AJAX.

**Green:** tombol ditentukan dari pesanan selesai yang belum direview.
Jika masih ada, tampilkan Rate Seller. Jika tidak ada tetapi buyer sudah
menulis review, tampilkan Edit My Review. Buyer tanpa pesanan yang memenuhi
syarat diarahkan ke View My Orders. Pengunjung tetap diarahkan melalui login.
Menghapus review membuat pesanan tersebut tersedia kembali untuk diulas.
Seluruh 72 tes review lulus dan tes browser memeriksa tombol setelah submit.

## 8. Audit sebelum merge dan responsivitas

**Red:** tes pesanan yang dihapus setelah validasi menghasilkan error server.
Tes browser menemukan toolbar kecil berukuran 32px, navbar tidak terpusat
pada desktop lebar, serta overflow review dengan judul/nama yang panjang.

**Green:** pesanan yang hilang ditangani sebagai validasi form; navbar memiliki
lebar dan margin terpusat yang konsisten serta kontrol minimal 40px pada ponsel.
Judul dan breadcrumb review membungkus teks panjang. Navbar diuji sebagai guest
dan member pada 320/360/390/768/1024/1280/1920px, termasuk pencarian, menu, dan bag.
Uji mobile mencakup halaman review, form, serta review dalam akun seller.
Tes tambahan juga memastikan edit tidak dapat mengganti order/reviewer/seller.

Temuan konfigurasi produksi global dilaporkan terpisah; paket ini tidak
mengklaim production settings atau seluruh modul lain sudah diaudit keamanan.

## Regresi yang diuji

- Create, edit, delete, input tidak valid, dan metode request.
- Login, kepemilikan, larangan review diri sendiri, dan manipulasi ID.
- Validasi rating, panjang teks, serta constraint database.
- Anonimitas, informasi berbasis login, escaping HTML, dan CSRF AJAX.
- Rata-rata global saat filter, distribusi rating, sorting, dan pagination.
- Helpful, balasan seller, laporan privat, dan akses halaman review seller.
- Komponen menu seller dan rating database secara terpisah.
  Integrasi template akun dan produk diuji melalui empat tes tambahan.Integrasi template akun dan produk diuji melalui empat tes tambahan.
- Browser: CRUD AJAX, filter tanpa reload, Helpful, laporan, balasan,
  tampilan desktop/ponsel, keyboard, kegagalan jaringan,
  dan fallback tanpa JavaScript.

## Hasil pengujian

- Tes modul review: 74 tes lulus.
- Tes browser review dan navbar: 7 tes lulus.
- Tes seluruh proyek: 202 tes lulus.
- Django system check: tidak ditemukan masalah.
- Coverage Python modul review dengan pengukuran cabang: 98,51%.
- Coverage `reviews/views.py`: 99,18%.

Coverage dihitung dari kode Python produksi pada app `reviews`.
Template, CSS, JavaScript, migrasi, dan kode tes tidak dihitung
dalam persentase tersebut. Perilaku browser diperiksa melalui
tes browser yang dijalankan secara terpisah.