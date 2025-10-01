# Kablosuz_Haberlesme

Bu proje jammerlı ortamda veri iletimi sağlamak amacıyla geliştirilen MAB (multi-armed bandit) tabanlı Thomson Sampling algoritmasını içermektedir.

2.4 GHZ merkez frekansında 20 MHz'lik iletim bandının 4 MHz genişliğinde 5 alt banta bölündüğü (2.402 GHz-2.418 GHz) sistemde jammer sinyali alt bantlar arasında her saniye rastgele atlama yapmaktadır. Amaç jammerın bulunduğu kanalı kullanmadan güvenilir şekilde veri iletimi gerçekleştirmektir. 

Sistem şöyle çalışır:

Sistem çalışmaya başladığı anda ilk 20 saniye coldstartı önlemek için warmup kısmıyla jammer davranışı analiz edilir. Bu süre boyunca kanal atlama mekanizması olarak energy detection+ FHSS kullanılır. Jammer patterni oluşturmak için kullanılan prior veriler sayesinde warmup sonrası algoritma sistemi tanıyarak yüksek doğruluk oranlarıyla çalışmaya başlar. Sistem ınput olarak anlık energy detection verilerini kullanır. Kanalın kullanılabilirlik (temiz-kirli) bilgisi bu veriden türetilir ve TS algoritmasının ödülü olarak kullanılır. 



