# Charm.li Maintenance Data Support List (2010-2013)

이미지의 12개 브랜드 카드를 기준으로 Charm.li에서 확인할 수 있는 2010~2013년도 정비 데이터 지원 현황입니다. 내일 파싱된 데이터를 보시고 수집 우선순위를 정하실 때 참고하세요.

| 번호 | 브랜드 라이브러리 (이미지 기준) | 데이터 지원 (2010-2013) | 대표 지원 모델 (Charm.li) |
| :--- | :--- | :---: | :--- |
| 1 | **Toyota & Lexus** | **O** | Corolla, Camry, Prius, RAV4, RX350 등 |
| 2 | **VW, Audi, Skoda, SEAT & CUPRA** | **O** | Audi A4, A6, Q5 / VW Golf, Jetta, Passat 등 |
| 3 | **Volvo Cars** | **O** | S60, S80, XC60, XC90 등 |
| 4 | **Mercedes-Benz** | **O** | C-Class, E-Class, S-Class, GLK 등 |
| 5 | **Peugeot, Citroën, DS, Opel...** | **X** | 1993년 이전 구형 모델 데이터만 존재 |
| 6 | **Porsche** | **O** | 911, Cayenne, Panamera, Boxster 등 |
| 7 | **Renault** | **X** | 1987년 이전 구형 모델 데이터만 존재 |
| 8 | **Tesla** | **X** | 리스트에 없음 (별도 소스 필요) |
| 9 | **Alfa Romeo, Maserati, Fiat, Jeep** | **O** | Fiat 500(2012~), Jeep Grand Cherokee 등 |
| 10 | **BMW & MINI** | **O** | 3 Series, 5 Series, 7 Series(F01), X5 등 |
| 11 | **Ford** | **O** | F-150, Focus, Mustang, Escape 등 |
| 12 | **Kia** | **O** | Optima, Sorento, Soul, Forte 등 |

## 수집 시 참고사항
- **강점**: 독일 3사(BMW, Benz, Audi)와 미국/일본/한국 주요 모델은 OEM 정비 지침서 수준으로 매우 상세함.
- **약점**: 테슬라 및 일부 유럽 전용 브랜드(푸조, 르노)의 데이터는 이 사이트에서 확보가 어려움.
- **활용**: 해당 연도 리스트에 있는 모델들의 ZIP 파일 주소는 `https://charm.li/bundle/{brand}/{year}/{model}/` 구조를 가짐.
