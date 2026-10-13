"""Why degrees are not distances: the length of one degree, and what swapping lon and lat does.

    uvx --with numpy python docs/tutorial/crs_demo.py
"""

import numpy as np

R = 6371.0  # km, the sphere used for great-circle distances


def haversine_km(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


print("緯度ごとの、経度 1 度の長さと、1 度 x 1 度の格子の面積")
print("緯度    経度1度(km)   緯度1度(km)   格子の面積(km2)")
for lat in (0, 35, 60, 80):
    lon_deg = haversine_km(0, lat, 1, lat)
    lat_deg = haversine_km(0, lat, 0, lat + 1)
    print(f"{lat:>3}度  {lon_deg:>10.1f}  {lat_deg:>12.1f}  {lon_deg * lat_deg:>14.0f}")

# Oslo (lon 10.75, lat 59.91) to Helsinki (lon 24.94, lat 60.17): about 790 km.
right = haversine_km(10.75, 59.91, 24.94, 60.17)
swapped = haversine_km(59.91, 10.75, 60.17, 24.94)  # each point's lat and lon passed in the wrong order
print(f"\nオスロからヘルシンキ (経度, 緯度の順に渡す): {right:.0f} km")
print(f"オスロからヘルシンキ (緯度, 経度を取り違えた): {swapped:.0f} km")
