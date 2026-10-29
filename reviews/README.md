# Review & Rating — GAIA

Penanggung jawab: Keisha Janice Maulina Napitupulu.

## Fitur

- CRUD review dengan rating 1–5, judul, komentar, dan pilihan anonim.
- Pilihan aspek layanan seller.
- Rata-rata rating, distribusi bintang, filter, sorting, dan pagination.
- Interaksi AJAX dengan perlindungan CSRF.
- Edit dan hapus hanya untuk pembuat review; review diri sendiri ditolak.
- Helpful, balasan seller, dan laporan review untuk admin.
- Tampilan responsif mengikuti desain GAIA.

## Batas Integrasi

Halaman review tersedia di `/reviews/seller/<seller_id>/`.
Halaman review seller yang login tersedia di `/reviews/account/`.

Menu Seller Reviews tersedia pada My Account khusus seller.
Rating pada bagian seller di halaman produk menggunakan data review
dan dapat diklik untuk membuka halaman review seller.

Review ditujukan langsung ke akun seller, bukan per produk.
Integrasi hanya menambahkan pemanggilan komponen review pada template
akun dan produk; logika akun, produk, dan transaksi tidak diubah.

## Verifikasi pembelian

Review tetap menilai akun seller. Review baru membutuhkan pesanan milik buyer
untuk seller tersebut, berstatus `completed`, dan belum memiliki review.
Satu pesanan hanya dapat memiliki satu review. Buyer dapat mengedit atau
menghapus review miliknya; seller hanya membalas review yang diterima.

Checkout menyimpan relasi produk dan seller pada `AccountOrder`.
Status setelah checkout tetap `awaiting_payment`: berhasil membuat pesanan
bukan bukti bahwa pembayaran atau pengiriman sudah selesai. Status pesanan
mengikuti proses transaksi kelompok. Untuk demo, staf dapat mengubah status
pesanan uji melalui admin Django yang sudah tersedia, tanpa mengubah akun
buyer/seller menjadi staf dan tanpa melewati validasi review.

Badge Verified buyer memeriksa status, pemilik, dan seller pada pesanan.
Ini verifikasi catatan pesanan aplikasi, bukan integrasi payment gateway.
Review lama/data demo yang tidak terhubung pesanan tetap disimpan tanpa badge.
Pesanan lama tidak dicocokkan otomatis berdasarkan judul barang.

Halaman detail pesanan menampilkan Review Seller setelah pesanan selesai,
atau Edit Seller Review jika sudah diulas. Form menampilkan pilihan pesanan
selesai sehingga buyer tidak perlu mengisi ID secara manual.

## Menjalankan

Jalankan dari root proyek:

```powershell
.\env\Scripts\python.exe manage.py migrate
.\env\Scripts\python.exe manage.py runserver
```

## Pengujian

Tes backend:

```powershell
.\env\Scripts\python.exe manage.py test reviews --noinput
```

Dependency dan tes browser:

```powershell
.\env\Scripts\python.exe -m pip install -r reviews/requirements-dev.txt
$env:GAIA_TEST_BROWSER = "C:\Program Files\Google\Chrome\Application\chrome.exe"
.\env\Scripts\python.exe manage.py test reviews.e2e --noinput
```

Tes menggunakan database pengujian. Catatan TDD tersedia di [TDD.md](TDD.md).

## Data Demo Opsional

Gunakan ID seller yang sudah memiliki produk:

```powershell
.\env\Scripts\python.exe manage.py seed_reviews --seller 1 --count 50
```

Data diberi label [Demo] dan tidak digandakan saat perintah dijalankan ulang.
Menambahkan 50 review tidak otomatis menambahkan 50 produk.
## Tombol pada halaman seller

Rate Seller hanya ditawarkan kepada buyer yang masih memiliki pesanan selesai
yang belum direview. Jika semua sudah diulas, tombol menjadi Edit My Review.
Buyer tanpa pesanan yang memenuhi syarat diarahkan ke View My Orders.
Pengunjung tetap masuk melalui login. Aturan ini berlaku pada halaman penuh
dan respons filter AJAX; pemeriksaan backend tetap berlaku pada setiap POST.

## Pemeriksaan sebelum merge

Audit tambahan memeriksa order yang hilang saat submit, manipulasi identitas
saat edit, dan overflow teks panjang. Navbar bersama diuji pada 320–1920px
sebagai guest/member di halaman produk, review, akun, orders, wishlist, dan chat.
Tes browser memeriksa pencarian mobile, menu, bag, form review, dan akun seller.
Konfigurasi produksi global dan layout checkout terpisah memerlukan pemeriksaan
deployment kelompok; kelulusan tes lokal bukan jaminan keamanan seluruh aplikasi.
