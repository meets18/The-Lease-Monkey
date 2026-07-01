p_sw = (26.787651, 75.833059)
p_se = (26.786722, 75.838976)
p_ne = (26.789209, 75.839725)
p_nw = (26.790382, 75.833765)

def interpolate(x, y):
    lat = (1 - x) * (1 - y) * p_sw[0] + x * (1 - y) * p_se[0] + x * y * p_ne[0] + (1 - x) * y * p_nw[0]
    lng = (1 - x) * (1 - y) * p_sw[1] + x * (1 - y) * p_se[1] + x * y * p_ne[1] + (1 - x) * y * p_nw[1]
    return {"lat": round(lat, 6), "lng": round(lng, 6)}

# 2 rows of plots separated by an East-West road in the middle (y=0.45 to y=0.55)
# 6 columns of plots separated by North-South roads (width=0.03 relative)
columns = [
    (0.03, 0.16),
    (0.19, 0.32),
    (0.35, 0.48),
    (0.51, 0.64),
    (0.67, 0.80),
    (0.83, 0.96)
]
rows = [
    (0.04, 0.44), # South row
    (0.56, 0.96)  # North row
]

plots = []
plot_num = 101

# Let's create plots
for r_idx, (y_min, y_max) in enumerate(rows):
    # If r_idx is 1 (North row), let's number them 201-206, and South row 101-106
    prefix = 200 if r_idx == 1 else 100
    for c_idx, (x_min, x_max) in enumerate(columns):
        num = prefix + (c_idx + 1)
        # Polygon corners: SW, SE, NE, NW
        coords = [
            interpolate(x_min, y_min),
            interpolate(x_max, y_min),
            interpolate(x_max, y_max),
            interpolate(x_min, y_max)
        ]
        
        # Calculate center
        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        center = interpolate(center_x, center_y)
        
        plots.append({
            "number": str(num),
            "status": "available" if (num % 3 == 0) else ("reserved" if (num % 3 == 1) else "sold"),
            "price": f"${35000 + (num * 120):,}",
            "area": f"{1200 + (num * 5)} sqft",
            "facing": "North" if r_idx == 1 else "South",
            "coordinates": coords,
            "center": center
        })

import json
print(json.dumps(plots, indent=2))
