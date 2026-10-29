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

## Regresi yang diuji

- Create, edit, delete, input tidak valid, dan metode request.
- Login, kepemilikan, larangan review diri sendiri, dan manipulasi ID.
- Validasi rating, panjang teks, serta constraint database.
- Anonimitas, informasi berbasis login, escaping HTML, dan CSRF AJAX.
- Rata-rata global saat filter, distribusi rating, sorting, dan pagination.
- Helpful, balasan seller, laporan privat, dan akses halaman review seller.
- Komponen menu seller dan rating database secara terpisah.
  Integrasi ke halaman akun dan produk ditunda.
- Browser: CRUD AJAX, filter tanpa reload, Helpful, laporan, balasan,
  tampilan desktop/ponsel, keyboard, kegagalan jaringan,
  dan fallback tanpa JavaScript.

## Hasil pengujian

- Tes modul review: 42 tes lulus.
- Tes browser review: 4 tes lulus.
- Tes seluruh proyek setelah sinkronisasi main: 170 tes lulus.
- Django system check: tidak ditemukan masalah.
- Coverage Python modul review dengan pengukuran cabang: 99,07%.
- Coverage `reviews/views.py`: 100%.

Coverage dihitung dari kode Python produksi pada app `reviews`.
Template, CSS, JavaScript, migrasi, dan kode tes tidak dihitung
dalam persentase tersebut. Perilaku browser diperiksa melalui
tes browser yang dijalankan secara terpisah.