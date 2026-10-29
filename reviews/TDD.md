# Catatan TDD Review & Rating

CRUD awal sudah dikerjakan sebelumnya. Tes regresi melindungi fitur tersebut;
catatan ini tidak mengklaim seluruh kode awal dibuat dengan TDD.
Siklus berikut benar-benar menjalankan tes gagal sebelum memperbaiki kode.

## 1. Data demo yang dapat diulang

**Red:** test_seed_is_repeatable_and_preserves_existing_review gagal dengan
Unknown command: seed_reviews.

**Green:** implementasi command seed_reviews menambahkan data berlabel [Demo]
menggunakan get_or_create dalam transaksi. Tes dijalankan dua kali; pertama
membuat lima review, kedua nol. Review awal tetap utuh.

**Refactor:** validasi seller dan jumlah data, lalu tambah pengujian default 50.

## 2. Melindungi akun pengguna yang sudah ada

**Red:** test_seed_does_not_impersonate_an_existing_real_account gagal karena
command semula menggunakan akun yang namanya cocok dengan nama demo.

**Green:** command menolak akun yang sudah mempunyai password.

Tes tambahan untuk akun aktif tanpa password juga ditulis terlebih dahulu.
Tes itu gagal, lalu aturan diperbaiki: akun demo baru dibuat nonaktif; akun
aktif atau akun berpassword yang sudah ada ditolak. Transaksi membatalkan
perubahan jika terjadi benturan.

## 3. Feedback ketika AJAX gagal

**Red:** tes browser memutus request Helpful. Pesan status tetap tersembunyi.

**Green:** helper status mencari area status pada halaman jika form aksi tidak
memiliki area pesan sendiri. Pengguna mendapat pesan error dan tombol aktif lagi.

## 4. Akses rating lewat keyboard

**Red:** tes browser memilih rating 3 lalu menekan ArrowRight. Rating 4 tidak terpilih
karena DOM radio diurutkan terbalik demi CSS bintang.

**Green:** radio dikembalikan ke urutan 1–5. CSS :has() mengatur highlight bintang
tanpa membalik urutan DOM. Klik dan navigasi keyboard sama-sama bekerja.

## Regresi yang diuji

- Create, edit, delete, data tidak valid, dan request yang tidak diizinkan.
- Login, kepemilikan, larangan review diri sendiri, dan manipulasi ID melalui POST.
- Validasi rating/panjang teks dan constraint database.
- Anonimitas, informasi berbasis login, escaping HTML, serta CSRF pada AJAX.
- Rata-rata global tetap sama saat filter, distribusi, sorting, pagination.
- Helpful, balasan seller, laporan privat, dan akses halaman review seller.
- Komponen menu seller dan rating database diuji secara terpisah; integrasi ke halaman akun dan produk ditunda.
- Browser: CRUD AJAX, filter tanpa reload, Helpful/Report/balasan, desktop/ponsel,
  keyboard, error jaringan, dan fallback tanpa JavaScript.

Hasil final dan log red/green disertakan dalam paket pembaruan, folder evidence.
Coverage hanya menghitung kode Python produksi pada app reviews, termasuk cabang
kondisi; tidak menghitung template, CSS, JavaScript, migrasi, atau kode tes.
