from flask import Flask, render_template, request, jsonify
import pandas as pd
import os
import re
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def parse_table(file_path):
    try:
        # Извлечение годов из заголовков
        header_df = pd.read_excel(file_path, sheet_name=0, header=None, nrows=4, usecols="C,D")
        
        years = []
        for _, row in header_df.iterrows():
            for cell in row:
                if pd.notnull(cell):
                    match = re.search(r'\d{4}', str(cell))
                    if match:
                        years.append(match.group())
        
        if len(years) < 2:
            raise ValueError("Не найдены годы в заголовках")
        
        year1, year2 = years[:2]
        
        # Чтение основных данных
        df = pd.read_excel(file_path, sheet_name=0, header=None, 
                          skiprows=6,  # Пропускаем первые 6 строк заголовков
                          usecols="A,C,D", 
                          names=['category', year1, year2],
                          thousands=',')
        
        # Очистка данных
        # df = df.dropna(subset=['category'])
        # df['category'] = df['category'].astype(str).str.strip()
        df = df.replace({'—': 0, '-': 0})
        df[year1] = pd.to_numeric(df[year1], errors='coerce').fillna(0)
        df[year2] = pd.to_numeric(df[year2], errors='coerce').fillna(0)
        
        # Определение разделов и итоговых строк
        sections = []
        current_section = None

        # Индексы итоговых строк в DataFrame
        total_indices = {
            6: 'Долгосрочные активы',   # Строка 13 Excel
            16: 'Текущие активы',       # Строка 23 Excel
            27: 'Собственный капитал',  # Строка 34 Excel
            33: 'Долгосрочные обязательства',  # Строка 40 Excel
            40: 'Текущие обязательства'        # Строка 47 Excel
        }
        for idx, row in df.iterrows():
            print(idx, row[year1], row[year2])
        current_assets = df.iloc[16]
        current_liabilities = df.iloc[40]
        inventory = df.iloc[8]
        cash = df.iloc[14]
        other_current_assets = df.iloc[15]
        # Расчет коэффициентов ликвидности
        liquidity = [
            {
                'indicator': 'Коэффициент текущей ликвидности',
                year1: round(current_assets[year1] / current_liabilities[year1], 3),
                year2: round(current_assets[year2] / current_liabilities[year2], 3)
            },
            {
                'indicator': 'Коэффициент быстрой ликвидности',
                year1: round((current_assets[year1] - inventory[year1]) / current_liabilities[year1], 3),
                year2: round((current_assets[year2] - inventory[year2]) / current_liabilities[year2], 3)
            },
            {
                'indicator': 'Коэффициент абсолютной ликвидности',
                year1: round((cash[year1] + other_current_assets[year1]) / current_liabilities[year1], 3),
                year2: round((cash[year2] + other_current_assets[year2]) / current_liabilities[year2], 3)
            }
        ]
        fin = [
            {
                'indicator': 'Коэффициент независимости',
                year1: round(df.iloc[27][year1]/df.iloc[42][year1], 3),
                year2: round(df.iloc[27][year2]/df.iloc[42][year2], 3)
            },
            {
                'indicator': 'Коэффициент финансовой устойчивости',
                year1: round((df.iloc[33][year1] + df.iloc[27][year1]) / df.iloc[42][year1], 3),
                year2: round((df.iloc[33][year2] + df.iloc[27][year2]) / df.iloc[42][year2], 3)
            },
            {
                'indicator': 'Коэффициент финансовой зависимости',
                year1: round(df.iloc[42][year1] / df.iloc[27][year1], 3),
                year2: round(df.iloc[42][year2] / df.iloc[27][year2], 3)
            },
            {
                'indicator': 'Коэффициент соотношения заемных и собственных средств',
                year1: round((df.iloc[33][year1] + df.iloc[40][year1]) / df.iloc[27][year1], 3),
                year2: round((df.iloc[33][year2] + df.iloc[40][year2]) / df.iloc[27][year2], 3)
            },
            {
                'indicator': 'Коэффициент долгосрочного привлечения заемных средств',
                year1: round(df.iloc[29][year1]/(df.iloc[29][year1] + df.iloc[27][year1]) , 3),
                year2: round(df.iloc[29][year2]/(df.iloc[29][year2] + df.iloc[27][year2]) , 3)
            },
            {
                'indicator': 'Коэффициент маневренности',
                year1: round((df.iloc[27][year1] + df.iloc[33][year1] - df.iloc[6][year1]) / df.iloc[27][year1], 3),
                year2: round((df.iloc[27][year2] + df.iloc[33][year2] - df.iloc[6][year2]) / df.iloc[27][year2], 3)
            }            
        ]
        print(current_liabilities[year1])
        for idx, row in df.iterrows():
            category = row['category']
            
            # Обработка итоговых строк
            if idx in total_indices:
                section = total_indices[idx]
                sections.append({
                    'section': section,
                    'item': 'Итого',
                    year1: round(row[year1], 3),
                    year2: round(row[year2], 3),
                    'is_total': True
                })
                continue
            
            # Определение текущего раздела
            if idx < 5:  # Долгосрочные активы (строки 7-12 Excel)
                current_section = 'Долгосрочные активы'
            elif 8 <= idx <= 15:  # Текущие активы (строки 15-22 Excel)
                current_section = 'Текущие активы'
            elif 20 <= idx <= 26:  # Собственный капитал (строки 27-33 Excel)
                current_section = 'Собственный капитал'
            elif 29 <= idx <= 32:  # Долгосрочные обязательства (строки 36-39 Excel)
                current_section = 'Долгосрочные обязательства'
            elif 35 <= idx <= 39:  # Текущие обязательства (строки 42-46 Excel)
                current_section = 'Текущие обязательства'
            else:
                current_section = None

            if current_section:
                sections.append({
                    'section': current_section,
                    'item': category,
                    year1: row[year1],
                    year2: row[year2],
                    'is_total': False
                })

        return {
            'years': [year1, year2],
            'sections': sections,
            'section_names': list({s['section'] for s in sections}),
            'liquidity': liquidity,
            'fin': fin
        }
    
    except Exception as e:
        print(f"Ошибка парсинга: {str(e)}")
        return {'years': [], 'sections': [], 'section_names': []}
    
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            return jsonify({'success': False, 'error': 'Файл не выбран'})
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        data = parse_table(file_path)
        
        if not data['years']:
            return jsonify({'success': False, 'error': 'Ошибка обработки файла'})
        
        # Преобразование типов для сериализации
        def convert_types(obj):
            if isinstance(obj, dict):
                return {k: convert_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(v) for v in obj]
            elif hasattr(obj, 'item'):
                return obj.item()
            else:
                return obj
        
        return jsonify(convert_types({
            'success': True,
            'years': data['years'],
            'sections': data['sections'],
            'section_names': data['section_names'],
            'liquidity': data.get('liquidity', []),
            'fin': data.get('fin', [])
        }))
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)