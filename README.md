# Kablosuz_Haberlesme

Bu proje jammerlı ortamda veri iletimi sağlamak amacıyla Reinforcement Learning kapsamında MAB (multi-armed bandit) tabanlı Thomson Sampling (TS) algoritmasını içermektedir.

2.4 GHZ merkez frekansında 20 MHz'lik iletim bandının 4 MHz genişliğinde 5 alt banta bölündüğü (2.402 GHz-2.418 GHz) sistemde jammer sinyali alt bantlar arasında her saniye rastgele atlama yapmaktadır. Amaç jammerın bulunduğu kanalı kullanmadan, güvenilir şekilde veri iletimi gerçekleştirmektir. 

Sistem çalışmaya başladıktan sonraki ilk 20 saniye cold startı önlemek,güvenli başlangıç yapmak ve jammer davranışını analiz etmek amacıyla warmup gerçekleştirilir.Bu sayede model öğrenmeye başlamadan önce parametrelerin nasıl bir dağılıma sahip olabileceğini tanımlar. Warmup boyunca kanal atlama mekanizması olarak yalnızca energy detection + FHSS kullanılır. Jammer patterni oluşturmak için kullanılan prior veriler sayesinde warmup sonrasında algoritma sistemi tanıyarak yüksek doğruluk oranlarıyla çalışmaya başlar. Algoritma iletim boyunca input olarak anlık energy detection verilerini kullanır. Kanalın kullanılabilirlik (temiz-kirli) bilgisi bu veriden türetilir. 

Ortamın gürültü düzeyine bağlı değişen adaptif bir threshold bulunmaktadır. Belirlenen eşik değerinin değişen ortam gürültüsüne bağlı(cep telefonları,wifi,bluetooth vb. kaynaklı her türlü yabancı sinyal) sistemi yanıltmaması için threshold adaptif olarak güncellenir. 

MAB yaklaşımı,karar vericinin sınırlı sayıda seçenek arasından (bu projede iletim kanalları) tekrar tekrar seçim yapması gereken durumlarda kullanılır. Her seçim sonucunda elde edilen ödül (seçilen ve iletim yapılan kanalın jammersız olduğu durum) ve ceza (jammerlı kanal) sayaçları kanalların gelecekte kullanım durumlarını belirlemek için kullanılır. Her bir saniyelik slotlarda ED'dan gelen anlık veriler işlenir. TS Beta dağılımı yardımıyla her kanal için (α başarıya verilen ağırlık / β başarısızlığa verilen ağırlık) başarı/başarısızlık değerlerini günceller. Her slot sonunda en yüksek doğruluk değerine sahip kanal TS ile seçilir. ED verilerinin belirlenen eşik değerinin altında (ödül, α=1) veya üstünde(ceza, β=0) olma durumuna göre kanalların doğruluk değerleri güncellenir. Doğruluk değerleri belirli oranda discounting ile güncellenir; böylece yeni koşullar ağır basar, eski verilerin katkısı giderek azalır ancak sıfırlanmaz.Bu sayede sistemin ortam koşullarına adaptasyonu hızlanır. Mevcut kanalın temiz olduğu durumlar için eşiğe küçük bir histerezis payı eklenir;bu sayede gereksiz kanal atlamanın önüne geçilmiş olur. 
NEDEN TS? HER KANALIN BAŞARI OLASILIĞINI BELİRSİZLİKLE BİRLİKTE HESAPLAR,KEŞİF KULLANIM DENGESİNİ OTOMATİK KURAR. unutma katsayısı ortam değiştikiçe eskşi sayımların etkisi azalır

Amaç iletim boyunca minimum kanal değişimi yapmak, gereken durumlarda modülasyonu değiştirmek ve jammer varlığında kesintisiz veri iletimi sağlamaktır. 
--
