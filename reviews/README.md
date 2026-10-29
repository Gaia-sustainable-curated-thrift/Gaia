# Review & Rating — GAIA

Penanggung jawab: Keisha Janice Maulina Napitupulu (2506551232).

Modul ini mengelola pengalaman pengguna terhadap seller. Tampilan mengikuti frame
Seller Reviews & Ratings dan Write a Seller Review pada
[Figma GAIA](https://www.figma.com/design/gTTsLkfL1qaaPdEomnRfKf/Gaia?node-id=365-3404).

## Fitur

- CRUD review: rating 1–5, judul, komentar, anonim, dan tiga aspek layanan.
- Daftar publik, rata-rata global, distribusi bintang, filter dari database,
  urutan Newest/Helpful/Rating, dan pagination enam review per halaman.
- Form create/edit/delete memakai fetch AJAX dengan CSRF. Link filter dan urutan
  memperbarui daftar tanpa reload. Form dan link tetap berfungsi tanpa JavaScript.
- Pembuat review saja yang boleh edit/hapus. Seller tidak boleh mereview dirinya.
- Guest melihat isi review, tetapi nama reviewer non-anonim hanya ditampilkan
  setelah login. Review anonim tetap anonim bagi pengguna lain yang sudah login.
- Pengguna login dapat menandai Helpful dan membatalkannya. Pembuat review dan
  seller terkait tidak dapat memberi suara pada review tersebut.
- Seller terkait dapat menulis, mengedit, dan menghapus balasan.
- Pengguna login dapat melaporkan review, sekali per pengguna per review.
  Isi laporan hanya dikelola lewat Django Admin oleh pengguna yang berizin.
- Seller Reviews tersedia di sidebar My Account khusus seller.
- Rating pada detail produk mengambil data Review asli dan tertaut ke daftar review.
- Bootstrap Grid 5.3.8 disimpan lokal, dilengkapi CSS GAIA yang dibatasi ke halaman review.

Proyek belum memiliki field role seller. Untuk integrasi saat ini, seller dikenali
dari kepemilikan produk atau riwayat received_reviews. Pengguna biasa yang hanya
menulis review tidak mendapat menu Seller Reviews.

## Batas integrasi

Review belum memverifikasi transaksi selesai: model transaksi aktual belum tersedia
pada snapshot proyek ini. Karena itu tidak ada badge Verified buyer atau klaim
Completed purchase. Pengguna login selain seller dapat menulis review pengalaman.
Hubungkan ke model transaksi bersama Danar ketika kontrak datanya sudah disepakati.

Public API eksternal, minimal 50 data utama marketplace, README kelompok, dan
deployment merupakan persyaratan kelompok. Perintah seed di bawah menyediakan
50 review sintetis; ini tidak otomatis menjadikan katalog produk berisi 50 produk.
README utama yang masih memuat 10 modul perlu diselaraskan oleh kelompok ke lima
modul: transaction—Danar, chat—Deva, review—Keisha, users—Salma, product—Kayla.
Tidak ada perubahan pada model, view, atau migrasi milik accounts/products.

## Menjalankan

Dari root proyek, memakai virtual environment yang sudah ada:

```powershell
.\env\Scripts\python.exe manage.py migrate
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py test reviews --noinput
.\env\Scripts\python.exe manage.py runserver
```

Halaman utama: /reviews/seller/<seller_id>/.
Sidebar seller: /reviews/account/. Akun reviewer dan seller harus berbeda.

Untuk data demo opsional, gunakan ID seller yang sudah memiliki produk:

```powershell
.\env\Scripts\python.exe manage.py seed_reviews --seller 1 --count 50
```

Perintah ini menambah review bertanda [Demo], tidak mengubah review lama, dan
bisa dijalankan ulang tanpa menggandakan data yang sama. Akun demo baru nonaktif
dengan password yang tidak dapat dipakai. Akun aktif yang kebetulan memakai nama
demo akan ditolak. Tidak ada data demo yang dimasukkan otomatis saat migrasi.

## Pengujian dan TDD

Lihat [TDD.md](TDD.md). Dependency pengembangan opsional:

```powershell
.\env\Scripts\python.exe -m pip install -r requirements-dev.txt
.\env\Scripts\python.exe -m coverage run --branch --source=reviews --omit="*/tests.py,*/e2e.py,*/migrations/*" manage.py test reviews --noinput
.\env\Scripts\python.exe -m coverage report -m
```

Tes browser menggunakan database pengujian Django, bukan database lokal:

```powershell
$env:GAIA_TEST_BROWSER = "C:\Program Files\Google\Chrome\Application\chrome.exe"
.\env\Scripts\python.exe manage.py test reviews.e2e --noinput
```

Jika Chrome tidak terpasang, arahkan GAIA_TEST_BROWSER ke Edge, atau instal
Chromium dengan `python -m playwright install chromium` lalu kosongkan variabel tersebut.
Override async-unsafe pada e2e hanya berlaku di proses tes karena API sinkron
Playwright memakai event loop; tidak ada perubahan setting aplikasi produksi.

Jalankan seluruh tes dari root proyek dengan `python manage.py test --noinput`.
Untuk build PWS, jalankan migrasi dan collectstatic melalui proses deployment
kelompok yang sudah digunakan. Modul ini tidak menambah kredensial, tidak
mengubah konfigurasi PWS, dan tidak melakukan merge/push.

## Titik integrasi minimal

- templates/accounts/layout.html: satu pemanggilan tag menu seller.
- templates/products/detail.html: satu pemanggilan tag rating seller.
- reviews/templatetags/review_tags.py: query dan tampilan kedua integrasi tersebut.
- Selain dua template itu, perubahan fitur berada pada app reviews dan asetnya.
