# CRM ilovasi texnik dokumentatsiyasi (UZ)

**Qamrov**
- CRM ilovasi: `crm/`
- CRM shablonlari: `templates/` ichidagi CRMga tegishlilari
- Bog'liq ilovalar: `xomashyo/`, `shop/` (faqat kesishma nuqtalari yoritiladi)

**Loyiha xaritasi**
- `config/urls.py`: umumiy routerlar va CRM prefiksi
- `crm/urls.py`: CRM URL patternlari
- `crm/views.py`: asosiy viewlar va biznes logika
- `crm/models.py`: asosiy model va hisoblash metodlari
- `crm/checker.py`: AJAX API endpointlari
- `crm/middleware.py`: admin/login cheklovi va security headerlar
- `crm/periodfilter.py`: admin uchun "oxirgi 15 kun" filtri
- `crm/admin.py`: admin panel konfiguratsiyasi
- `crm/utils.py`: bo'sh (placeholder)
- `crm/views copy.py`: URLga ulangan emas (arxiv nusxa)

**URL prefiksi**
- `config/urls.py` ichida CRM: `path('uy', include('crm.urls'))`
- Eslatma: prefiksda slash yo'q. Natijaviy URLlar `uy/...` yoki noto'g'ri `uyemployees/` kabi bo'lishi mumkin. Amalda tekshirish kerak. Odatdagi to'g'ri variant `uy/`.

**URL xaritasi (crm/urls.py)**
- `''` -> `HomeView` (name `home`) -> `templates/index.html`
- `oylik_yopish/<int:pk>/` -> `oylik_yopish` (name `oylik_yopish`)
- `yangi_oy_boshlash/<int:pk>/` -> `yangi_oy_boshlash` (name `yangi_oy`)
- `employees/` -> `EmployeeView` (name `employee`) -> `templates/employees_list.html`
- `employees/<int:pk>/` -> `EmployeeDetailView` (name `employee_detail`) -> `templates/employee_detail.html`
- `employees/create/` -> `EmployeeCreateView` (name `ishchi_create`) -> `templates/employees.html` (fayl mavjud emas)
- `employees/<int:pk>/delete/` -> `EmployeeDeleteView` (name `ishchi_delete`)
- `employees/<int:pk>/update/` -> `EmployeeUpdateView` (name `ishchi_update`)
- `products/` -> `ProductsView` (name `products`) -> `templates/product_list.html`
- `ish-qoshish/` -> `IshQoshishView` (name `ish_qoshish`) -> `templates/ish_qoshish.html`
- `sotuvlar/` -> `SotuvQoshish` (name `sotuvlar`) -> `templates/sotuv/sotuvlar.html`
- `sotuv/list/` -> `SotuvListView` (name `sotuv_list`) -> `templates/sotuv/sotuv_list.html`
- `sotuv/qoshish/` -> `sotuv_qoshish` (name `sotuv_qoshish`)
- `sotuv/<int:sotuv_id>/ochirish/` -> `sotuv_ochirish` (name `sotuv_ochirish`)
- `sotuv/detail/<int:pk>/` -> `SotuvDetailView` (name `sotuv_detail`) -> `templates/sotuv/sotuv.html`
- `sotuv/<int:sotuv_id>/pdf/` -> `sotuv_pdf` (name `sotuv_pdf`)
- `sotuv/<int:sotuv_id>/item/qoshish/` -> `sotuv_item_qoshish` (name `sotuv_item_qoshish`)
- `sotuv/item/<int:item_id>/tahrirlash/` -> `sotuv_item_tahrirlash` (name `sotuv_item_tahrirlash`)
- `sotuv/item/<int:item_id>/ochirish/` -> `sotuv_item_ochirish` (name `sotuv_item_ochirish`)
- `api/variant/<int:variant_id>/` -> `get_variant_info` (name `get_variant_info`)
- `kirimlar/` -> `KirimListView` (name `kirimlar`) -> `templates/kirim_list.html`
- `xaridorlar/` -> `XaridorListView` (name `xaridorlar`) -> `templates/xaridor_list.html`
- `xaridorlar/<int:pk>/` -> `XaridorDetailView` (name `xaridor_detail`) -> `templates/xaridor_detail.html`
- `xaridorlar/qoshish/` -> `xaridor_qoshish` (name `xaridor_qoshish`)
- `xaridorlar/<int:pk>/tahrirlash/` -> `xaridor_tahrirlash` (name `xaridor_tahrirlash`)
- `api/mahsulot/<int:mahsulot_id>/zakatovka-xomashyolar/` -> `checker.get_zakatovka_xomashyolar_api`
- `api/xomashyo/<int:xomashyo_id>/variants/` -> `checker.get_xomashyo_variants_api`
- `api/mahsulot/<int:mahsulot_id>/variants/` -> `checker.get_product_variants`
- `api/mahsulot/<int:mahsulot_id>/kroy-xomashyolar/` -> `checker.get_kroy_xomashyolar_api`

**Ruxsat va xavfsizlik**
- `is_admin(user)` va `AdminRequiredMixin`: faqat `is_staff` yoki `is_superuser`.
- `StaffRequiredMixin`: faqat `is_staff`.
- `crm/middleware.py` ichida `AdminOnlyMiddleware`: URL name bo'yicha login va admin cheklovi (name mosligi muhim).
- `SecurityHeadersMiddleware`: XSS va frame himoya headerlari.

**Viewlar va funksiyalar (crm/views.py)**

**Auth va ruxsat**
- `is_admin(user)`: foydalanuvchi login bo'lsa va staff/superuser bo'lsa True.
- `is_authenticated_user(user)`: login bo'lsa True. Hozirgi kodda ishlatilmaydi.
- `AdminRequiredMixin.test_func`: adminligini tekshiradi.
- `AdminRequiredMixin.handle_no_permission`: xabar beradi va `account_login`ga yuboradi.
- `StaffRequiredMixin.test_func`: staffligini tekshiradi.
- `StaffRequiredMixin.handle_no_permission`: xabar beradi va `account_login`ga yuboradi.

**Bosh sahifa**
- `HomeView.handle_no_permission`: login talab qiladi, xabar chiqaradi.
- `HomeView.get_context_data`: joriy oy sotuv va chiqimlarni hisoblaydi, foyda (`avg_profit * miqdor`), ishchilar soni va mahsulot qoldigini chiqaradi.

**Ishchilar**
- `oylik_yopish(request, pk)`: POST bo'lsa ishchi bo'yicha oylik yig'indisini hisoblaydi, `Oyliklar` yaratadi, har bir `Ish`ni `EskiIsh`ga ko'chiradi, `Ishchi.is_oylik_open=False` qiladi. Hozirgi kod barcha `Ish` yozuvlarini `status='yopilgan'` qiladi.
- `yangi_oy_boshlash(request, pk)`: POST bo'lsa ishchi uchun `is_oylik_open=True` qiladi.
- `EmployeeView.get_queryset`: ishchilarni ism/familiya bo'yicha tartiblaydi.
- `EmployeeView.get_context_data`: `IshchiCategory` ro'yxati va `is_admin` qo'shadi.
- `EmployeeCreateView.form_valid`: yangi ishchi yaratadi, success xabari.
- `EmployeeDeleteView.post`: ishchini o'chiradi; AJAX bo'lsa JSON qaytaradi.
- `EmployeeUpdateView.form_valid`: ishchi ma'lumotini yangilaydi, success xabari.
- `EmployeeDetailView.get_context_data`: joriy oy ishlar, mahsulotlar kesimi, avanslar va beriladigan summa hisoblanadi.

**Mahsulotlar**
- `ProductsView.get_context_data`: `is_admin` flag qo'shadi.

**Ish qo'shish (IshQoshishView)**
- `get`: ishchi, mahsulot va xomashyo ro'yxatini beradi (`teri`, `astar`, `padoj`).
- `post`: umumiy oqim.
- POST inputlari: `ishchi`, `mahsulot`, `soni`, `ish_sanasi`, `mustaqil_ish`, hamda turga qarab `kroy_xomashyo`, `teri_xomashyo[]`, `teri_variant[]`, `teri_sarfi_custom[]`, `astar_xomashyo`, `astar_variant`, `astar_sarfi_custom`, `zakatovka_xomashyo`, `padoj_xomashyo`, `padoj_variant`, `mahsulot_variant`, `variant_rang`, `variant_razmer`.
- Zakatovka: `mustaqil_ish` bo'lsa kroy xomashyosiz ish yoziladi va `zakatovka` jarayon xomashyosi yaratiladi. Aks holda kroy xomashyo miqdori kamayadi, `IshXomashyo` yozuvlari yaratiladi.
- Kroy/Rezak: bir nechta teri sarfi yoziladi (`TeriSarfi`), `IshXomashyo` yozuvlari yaratiladi. Astar bo'lsa astar miqdori kamayadi. Kroy jarayon xomashyosi yaratiladi.
- Kosib: padoj majburiy. `mustaqil_ish` bo'lsa zakatovkasiz ishlaydi; aks holda zakatovka miqdori kamayadi. `ProductVariant` stocki oshiriladi yoki yangi variant yaratiladi. Kosib jarayon xomashyosi yaratiladi.
- Boshqa turlar: faqat `Ish` yozuvi yaratiladi.
- `post` ichida `transaction.atomic` ishlatiladi. Debug sifatida `PRAGMA foreign_key_check` bor.
- `_get_or_create_jarayon_xomashyo`: jarayon xomashyosini topadi yoki yaratadi, miqdorini oshiradi.

**Sotuvlar**
- `SotuvQoshish.get_queryset`: qidiruv va sana filtri bilan sotuvlar ro'yxati.
- `SotuvQoshish.get_context_data`: bugungi/oylik/jami statistika, `Xaridor` va `ProductVariant` ro'yxati.
- `SotuvListView.get_queryset`: qidiruv, sana oraligi, to'lov holati, xaridor, summa oraligi va saralash filtrlari.
- `SotuvListView.get_context_data`: bugun/hafta/oy/jami statistikalar va filter uchun xaridorlar.
- `SotuvDetailView`: faqat `DetailView`; qo'shimcha kontekst qo'shmaydi.
- `sotuv_pdf`: reportlab orqali sotuv cheki PDF yaratadi.
- `sotuv_qoshish`: POSTda xaridor yaratish yoki tanlash, sotuv yaratish, itemlar qo'shish. `items` JSON bo'lmasa bitta mahsulot formatini qabul qiladi.
- `sotuv_item_qoshish`: mavjud sotuvga item qo'shadi, JSON natija qaytaradi.
- `sotuv_item_tahrirlash`: item narx/miqdorni yangilaydi, JSON qaytaradi.
- `sotuv_item_ochirish`: itemni o'chiradi, stock qaytariladi.
- `sotuv_ochirish`: sotuvni o'chiradi; itemlar o'chirilgani uchun stock qaytariladi.
- `get_variant_info`: variant narxi va stockini JSON qaytaradi.

**Kirimlar**
- `KirimListView.get_queryset`: qidiruv va sana filtri. `Q(mahsulot__nomi)` ishlatilgan, `Kirim` modelida bunday field yo'q (xato bo'lishi mumkin).
- `KirimListView.get_context_data`: bugungi/oylik/jami kirim summalari.

**Xaridorlar**
- `XaridorListView.get_queryset`: ism/telefon bo'yicha qidiruv.
- `XaridorListView.get_context_data`: xaridor bo'yicha jami xarid va xaridlar soni hisoblanadi.
- `XaridorDetailView.get_context_data`: xaridorning sotuvlari va jami xarid summasi.
- `xaridor_qoshish`: POSTda yangi xaridor yaratadi.
- `xaridor_tahrirlash`: POSTda xaridor ma'lumotini yangilaydi.

**Chiqimlar (CRM ichida)**
- `ChiqimListView.get_context_data`: bugungi/oylik/jami chiqimlar, xomashyo va chiqim turlari ro'yxati.
- `chiqim_ochirish`: chiqimni o'chiradi.
- Eslatma: CRM `ChiqimListView` URLga ulangan emas; xuddi shu nom `xomashyo/views.py`da ham bor.

**AJAX API (crm/checker.py)**
- `get_zakatovka_xomashyolar_api`: mahsulot bo'yicha zakatovka xomashyo ro'yxati.
- `get_xomashyo_variants_api`: xomashyo variantlari.
- `get_kroy_xomashyolar_api`: mahsulot bo'yicha kroy xomashyo ro'yxati.
- `get_product_variants`: mahsulot variantlari (stock va narx).

**Model va metodlar (crm/models.py)**

**Category**
- Maqsad: mahsulot kategoriyasi.
- `__str__`: nomini qaytaradi.

**Product**
- Muhim fieldlar: `status`, `category`, `nomi`, `narxi`, `avg_profit`, `narx_kosib`, `narx_zakatovka`, `narx_kroy`, `narx_rezak`, `narx_pardoz`, `teri_sarfi`, `astar_sarfi`.
- `product_total_stock()`: barcha variant stocklarini yig'adi.
- `update_total_quantity()`: `variants` yig'indisini `soni`ga yozadi.
- `total_stock` (property): variantlar stock yig'indisi.
- `get_price_for_category(category_name)`: ishchi turi bo'yicha narx.
- `__str__`: nom.

**ProductVariant**
- Muhim fieldlar: `product`, `stock`, `price`, `rang`, `razmer`, `type`, `sku`, `barcode`.
- `save()`: SKU avtomatik generatsiya qiladi.
- `delete()`: mahsulot `soni`ni qayta hisoblaydi.
- `__str__`: mahsulot + rang/razmer.

**IshchiCategory**
- `__str__`: nom.

**Oyliklar**
- `__str__`: ishchi, sana, oylik.

**EskiIsh**
- `__str__`: ishchi va mahsulot.

**Ishchi**
- `umumiy_oylik()`: `status='yangi'` ishlar narxini yig'adi.
- `ishlar_soni()` (staticmethod): kosib turidagi ishlar soni.
- `oy_mahsulotlar()`: joriy oy mahsulotlar kesimi.
- `__str__`: ism/familiya.

**IshXomashyo**
- `jami_narx` (property): birlik narxdan yoki variant/xomashyo narxidan hisoblaydi.
- `clean()`: miqdor va variant tegishliligi, real xomashyo miqdori tekshiruvi.
- `save()`: birlik narxni to'ldiradi, validatsiya qiladi. Jarayon xomashyoda stock kamaytirmaydi; real xomashyoda view javobgar.
- `__str__`: ish va xomashyo/variant.

**Ish**
- `save()`: ishchi turiga qarab narxni hisoblaydi. `rezak` sharti `self.ishchi.turi == "rezak"` bo'lgani uchun ishlamasligi mumkin.
- `__str__`: mahsulot nomi.
- Saqlashdan keyin kosib bo'lsa `Product.soni` qayta hisoblanadi.

**ChiqimTuri**
- `__str__`: nom.

**Chiqim**
- `sum_prices()` (staticmethod): joriy oy jami chiqim.
- `__str__`: nom.

**ChiqimItem**
- `save()`: yangi xomashyo qatori bo'lsa `XomashyoHarakat` yaratadi (kirim sifatida).
- `__str__`: nom va narx.

**Xaridor**
- `__str__`: ism.

**Sotuv**
- `update_summa()`: itemlardan jami va yakuniy summani hisoblaydi.
- `save()`: yangi sotuvda avtomatik `Kirim` yaratadi.
- `__str__`: id, xaridor, summa.

**SotuvItem**
- `save()`: jami hisoblaydi, stock tekshiradi, stockni kamaytiradi yoki farqni qo'llaydi, `Product.update_total_quantity()` va `Sotuv.update_summa()`ni chaqiradi.
- `delete()`: stockni qaytaradi, sotuv summasini yangilaydi.
- `__str__`: variant, miqdor, narx.

**Kirim**
- `__str__`: sana, summa, xaridor.

**Feature**
- `__str__`: name.

**Avans**
- `__str__`: ishchi va summa.

**TeriSarfi**
- `save()`: faqat yozuv yaratadi, xomashyo miqdorini kamaytirmaydi.
- `delete()`: variant/xomashyo miqdorini qaytaradi.
- `__str__`: ish, xomashyo, miqdor.

**Admin va qo'shimcha (crm/admin.py, crm/periodfilter.py)**
- `OyliklarAdmin.formfield_for_dbfield`: oylik inputini masklaydi.
- `AvansAdmin.formfield_for_dbfield`: amount inputini masklaydi.
- `SotuvAdmin.get_queryset`: xaridor va itemlarni prefetch qiladi.
- `SotuvItemAdmin.get_queryset`: sotuv/mahsulot/variantni select qiladi.
- `Last15DaysFilter.lookups` va `Last15DaysFilter.queryset`: oxirgi 15 kun filtri.

**Templates (CRMga tegishlilar)**
- `templates/index.html`: HomeView statistikasi. Kontext: `products`, `total_profit`, `monthly_outlays`, `salary_sum`, `employees`.
- `templates/employees_list.html`: ishchi ro'yxati va yaratish modali. Kontext: `ishchilar`, `ishchi_turlari`, `is_admin`.
- `templates/employee_detail.html`: ishchi tafsilotlari, ishlar, avanslar. Kontext: `ishchi`, `ishlar`, `oy_stat`, `ish_soni`, `avanslar`, `total_avans`, `beriladi`.
- `templates/product_list.html`: mahsulotlar. Modal form backendga ulangan emas.
- `templates/ish_qoshish.html`: ish biriktirish. Kontext: `ishchilar`, `mahsulotlar`, `terilar`, `astarlar`, `padojlar`. JS `api` endpointlarga murojaat qiladi.
- `templates/sotuv/sotuvlar.html`: sotuv yaratish va statistika. Kontext: `sotuvlar`, `xaridorlar`, `mahsulotlar`, `bugungi_sotuv`, `bugungi_soni`, `oylik_sotuv`, `jami_sotuv`.
- `templates/sotuv/sotuv_list.html`: sotuvlar filtri va ro'yxat. Kontext: `sotuvlar`, `xaridorlar`, `page_obj`.
- `templates/sotuv/sotuv.html`: sotuv tafsilotlari. Kontext: `sotuv`. Shablon `variants`ni kutadi, lekin view bermaydi.
- `templates/kirim_list.html`: kirimlar ro'yxati va statistika. Kontext: `kirimlar`, `bugungi_kirim`, `oylik_kirim`, `jami_kirim`.
- `templates/xaridor_list.html`: xaridorlar ro'yxati va modal. Kontext: `xaridorlar`, `jami_xaridorlar`.
- `templates/xaridor_detail.html`: xaridor tafsilotlari va sotuvlar. Kontext: `xaridor`, `sotuvlar`, `jami_xarid`, `xaridlar_soni`. Shablon `top_mahsulotlar`ni kutadi, view bermaydi.
- `templates/chiqim.html`: chiqimlar UI. Kontextda `chiqimlar`, `xomashyo_json`, `cats_json`, `yetkazib_beruvchilar` bo'lishi kerak. CRM `ChiqimListView` bularni to'liq bermaydi.
- `templates/ish_qoshish copy.html`: ishlatilmaydigan nusxa (URLga ulanmagan).
- `templates/employees.html`: view tomonidan ishlatiladi, lekin fayl yo'q.

**Biznes qoidalar va yon ta'sirlar**
- Sotuv item saqlansa stock kamayadi, o'zgarsa farq bo'yicha yangilanadi, o'chirilsa stock qaytariladi.
- Sotuv o'chirilsa, itemlar o'chiriladi va stock qaytariladi.
- Sotuv yaratilganda `Kirim` avtomatik yaratiladi; keyin sotuv summasi o'zgarsa `Kirim` avtomatik yangilanmaydi.
- Ish qo'shishda turga qarab jarayon xomashyosi (`kroy`, `zakatovka`, `kosib`) yaratilib miqdori oshadi.
- `TeriSarfi` saqlanganda teri miqdori kamaymaydi; o'chirilsa qaytariladi.

**Muammolar va mos kelmasliklar (hozirgi kod)**
- `EmployeeCreateView` `templates/employees.html`ga bog'langan, fayl yo'q.
- `employees_list.html` JS ichida `fetch(/employees/...)` ishlatiladi; CRM prefiksi bilan mos emas.
- `ish_qoshish.html` JS `fetch(/uyapi/...)` qiladi, URLlar `api/...` sifatida yozilgan.
- `sotuv_list.html` JS `form.action = /sotuv/...` qiladi; prefiks bilan mos emas.
- `sotuv.html` `fetch(/api/sotuv/item/<id>/)` endpointi yo'q.
- `sotuv.html` shablon `variants`ni kutadi, view bermaydi.
- `KirimListView.get_queryset` ichida `mahsulot__nomi` filtri `Kirim`da mavjud emas.
- `AdminOnlyMiddleware` URL name ro'yxati `ishchi_*` nomlari bilan mos emas.
- `Ish.save` ichidagi `rezak` sharti noto'g'ri bo'lishi mumkin (`turi` FK).
- `oylik_yopish` barcha `Ish` yozuvlarini `yopilgan` qiladi.
