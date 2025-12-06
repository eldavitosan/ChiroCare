import os

file_path = r'c:\Users\black\ChiroCare\templates\admin\reportes_dashboard.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# The broken block to find (normalized)
broken_block = """                data: {
                    labels: {{ labels_ingresos | tojson }
    },
        datasets: [{
            label: 'Ingresos ($)',
            data: {{ data_values_ingresos | tojson }},
        backgroundColor: 'rgba(75, 192, 192, 0.6)'
                    }]
                },"""

# The correct block
correct_block = """                data: {
                    labels: {{ labels_ingresos | tojson }},
                    datasets: [{
                        label: 'Ingresos ($)',
                        data: {{ data_values_ingresos | tojson }},
                        backgroundColor: 'rgba(75, 192, 192, 0.6)'
                    }]
                },"""

if broken_block in content:
    new_content = content.replace(broken_block, correct_block)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("FIX APPLIED")
else:
    print("BROKEN BLOCK NOT FOUND EXACTLY. Printing snippet:")
    start_marker = "new Chart(ctxIngresos, {"
    idx = content.find(start_marker)
    if idx != -1:
        print(content[idx:idx+400])
