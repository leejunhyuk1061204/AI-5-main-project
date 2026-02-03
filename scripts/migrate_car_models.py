import re

# 변환 매핑 정의
MANUFACTURERS = {
    '현대': 'Hyundai',
    '기아': 'Kia',
    '제네시스': 'Genesis',
    '쉐보레': 'Chevrolet',
    '르노코리아': 'Renault Korea',
    'KG모빌리티': 'KG Mobility',
    '쌍용': 'SsangYong'
}

MODELS = {
    '아반떼 (MD)': 'Elantra (MD)',
    '아반떼 (AD)': 'Elantra (AD)',
    '아반떼 (CN7)': 'Elantra (CN7)',
    '쏘나타 (YF)': 'Sonata (YF)',
    '쏘나타 (LF)': 'Sonata (LF)',
    '쏘나타 (DN8)': 'Sonata (DN8)',
    '그랜저 (HG)': 'Azera (HG)',
    '그랜저 (IG)': 'Azera (IG)',
    '그랜저 (GN7)': 'Azera (GN7)',
    '투싼 (ix)': 'Tucson (ix)',
    '투싼 (TL)': 'Tucson (TL)',
    '투싼 (NX4)': 'Tucson (NX4)',
    '싼타페 (DM)': 'Santa Fe (DM)',
    '싼타페 (TM)': 'Santa Fe (TM)',
    '싼타페 (MX5)': 'Santa Fe (MX5)',
    '모닝 (TA)': 'Morning (TA)',
    '모닝 (JA)': 'Morning (JA)',
    'K3 (YD)': 'Forte/K3 (YD)',
    'K3 (BD)': 'Forte/K3 (BD)',
    'K5 (TF)': 'Optima/K5 (TF)',
    'K5 (JF)': 'Optima/K5 (JF)',
    'K5 (DL3)': 'K5 (DL3)',
    'K7 (VG)': 'Cadenza/K7 (VG)',
    'K7 (YG)': 'Cadenza/K7 (YG)',
    'K8 (GL3)': 'K8 (GL3)',
    'K9 (KH)': 'K900/K9 (KH)',
    'K9 (RJ)': 'K900/K9 (RJ)',
    '스포티지 (R)': 'Sportage (R)',
    '스포티지 (QL)': 'Sportage (QL)',
    '스포티지 (NQ5)': 'Sportage (NQ5)',
    '쏘렌토 (XM)': 'Sorento (XM)',
    '쏘렌토 (UM)': 'Sorento (UM)',
    '쏘렌토 (MQ4)': 'Sorento (MQ4)',
    'G70 (IK)': 'G70 (IK)',
    'G80 (DH)': 'G80 (DH)',
    'G80 (RG3)': 'G80 (RG3)',
    'G90 (HI)': 'G90 (HI)',
    'G90 (RS4)': 'G90 (RS4)',
    'GV70 (JK1)': 'GV70 (JK1)',
    'GV80 (JX1)': 'GV80 (JX1)'
}

input_path = r'c:\Users\301\dev\AI-5-main-project\db\seed_car_models.sql'
output_path = r'c:\Users\301\dev\AI-5-main-project\db\seed_car_models_new.sql'

with open(input_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('INSERT INTO car_model_master'):
        new_lines.append("INSERT INTO car_model_master (manufacturer_ko, manufacturer_en, model_name_ko, model_name_en, model_year, fuel_type) VALUES\n")
        continue
    
    # 데이터 행인 경우 검색: ('제조사', '모델명', 연도, '연료')
    match = re.search(r"\('(.+?)', '(.+?)', (\d+), '(.+?)'\)([,;])", line)
    if match:
        m_ko, mod_ko, year, fuel, suffix = match.groups()
        m_en = MANUFACTURERS.get(m_ko, m_ko)
        mod_en = MODELS.get(mod_ko, mod_ko)
        
        new_line = f"('{m_ko}', '{m_en}', '{mod_ko}', '{mod_en}', {year}, '{fuel}'){suffix}\n"
        new_lines.append(new_line)
    else:
        new_lines.append(line)

with open(output_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"변환 완료: {output_path}")
