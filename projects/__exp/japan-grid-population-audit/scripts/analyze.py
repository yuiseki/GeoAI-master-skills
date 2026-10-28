"""Area-preserving comparison of census and GHSL grids.

Pure geometry helpers live here so small, known-answer tests run before remote data.
The command-line analysis is added only after those tests pass.
"""

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from pyproj import Transformer

EQUAL_AREA = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)


@lru_cache(maxsize=20000)
def _x(lon: float) -> float:
    value = EQUAL_AREA.transform(lon, 0.0)[0]
    if not math.isfinite(value):
        raise ValueError(f"invalid longitude: {lon}")
    return value


@lru_cache(maxsize=20000)
def _y(lat: float) -> float:
    value = EQUAL_AREA.transform(0.0, lat)[1]
    if not math.isfinite(value):
        raise ValueError(f"invalid latitude: {lat}")
    return value


def projected_area(bounds: tuple[float, float, float, float]) -> float:
    west, south, east, north = bounds
    if east <= west or north <= south:
        raise ValueError(f"empty or reversed rectangle: {bounds}")
    return (_x(east) - _x(west)) * (_y(north) - _y(south))


def overlap_area(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    west, south, east, north = (
        max(a[0], b[0]),
        max(a[1], b[1]),
        min(a[2], b[2]),
        min(a[3], b[3]),
    )
    return (
        0.0
        if west >= east or south >= north
        else projected_area((west, south, east, north))
    )


def overlap_fraction(
    source: tuple[float, float, float, float], target: tuple[float, float, float, float]
) -> float:
    """Area of source inside target, divided by source area (EPSG:6933)."""
    return overlap_area(source, target) / projected_area(source)


def mesh_bounds(code: str) -> tuple[float, float, float, float]:
    """JGD2011 3rd-mesh SW corner; longitude, latitude order."""
    if len(code) != 8 or not code.isascii() or not code.isdigit():
        raise ValueError(f"invalid third-mesh code: {code!r}")
    south = int(code[:2]) / 1.5 + int(code[4]) / 12 + int(code[6]) / 120
    west = 100 + int(code[2:4]) + int(code[5]) / 8 + int(code[7]) / 80
    return west, south, west + 1 / 80, south + 1 / 120


@dataclass(frozen=True)
class Tile:
    name: str
    west: float
    north: float
    width: float
    height: float
    values: np.ndarray

    def __post_init__(self):
        if self.values.ndim != 2 or self.width <= 0 or self.height <= 0:
            raise ValueError("tile must be a 2D grid with positive cell dimensions")

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        rows, cols = self.values.shape
        return (
            self.west,
            self.north - rows * self.height,
            self.west + cols * self.width,
            self.north,
        )

    def cell_bounds(self, row: int, col: int) -> tuple[float, float, float, float]:
        west = self.west + col * self.width
        north = self.north - row * self.height
        return west, north - self.height, west + self.width, north


def assemble_grid(
    rows: np.ndarray, cols: np.ndarray, values: np.ndarray, shape: tuple[int, int]
) -> np.ndarray:
    """Rebuild a complete raster from unordered Parquet rows; reject silent duplication."""
    rows, cols, values = (
        np.asarray(rows),
        np.asarray(cols),
        np.asarray(values, dtype=np.float64),
    )
    if len(rows) != len(cols) or len(rows) != len(values):
        raise ValueError("grid column lengths differ")
    if (
        np.any(rows < 0)
        or np.any(cols < 0)
        or np.any(rows >= shape[0])
        or np.any(cols >= shape[1])
    ):
        raise ValueError("grid index out of range")
    flat = rows.astype(np.int64) * shape[1] + cols.astype(np.int64)
    counts = np.bincount(flat, minlength=shape[0] * shape[1])
    if np.any(counts > 1):
        raise ValueError("duplicate grid cell")
    if np.any(counts == 0):
        raise ValueError("missing grid cell")
    if not np.all(np.isfinite(values)):
        raise ValueError("invalid grid value")
    grid = np.empty(shape, dtype=np.float64)
    grid[rows, cols] = values
    return grid


@dataclass(frozen=True)
class MeshEstimate:
    area_population: float
    center_population: float
    coverage: float
    overlap_cells: int


def estimate_mesh(
    mesh: tuple[float, float, float, float], tiles: tuple[Tile, ...]
) -> MeshEstimate:
    """Distribute each touched source cell by area; compare whole-cell centroid assignment."""
    area_population = 0.0
    center_population = 0.0
    covered = 0.0
    overlaps = 0
    mesh_area = projected_area(mesh)
    for tile in tiles:
        if overlap_area(mesh, tile.bounds) == 0:
            continue
        rows, cols = tile.values.shape
        col_start = max(0, math.floor((mesh[0] - tile.west) / tile.width))
        col_end = min(cols, math.ceil((mesh[2] - tile.west) / tile.width))
        row_start = max(0, math.floor((tile.north - mesh[3]) / tile.height))
        row_end = min(rows, math.ceil((tile.north - mesh[1]) / tile.height))
        for row in range(row_start, row_end):
            for col in range(col_start, col_end):
                cell = tile.cell_bounds(row, col)
                intersection = overlap_area(cell, mesh)
                if intersection <= 0:
                    continue
                value = float(tile.values[row, col])
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"invalid population in {tile.name}:{row}:{col}")
                area_population += value * intersection / projected_area(cell)
                covered += intersection
                overlaps += 1
                center_x = (cell[0] + cell[2]) / 2
                center_y = (cell[1] + cell[3]) / 2
                if mesh[0] <= center_x < mesh[2] and mesh[1] <= center_y < mesh[3]:
                    center_population += value
    coverage = covered / mesh_area
    if coverage > 1 + 1e-8:
        raise ValueError(f"overlapping source tiles cover mesh {coverage} times")
    return MeshEstimate(
        area_population, center_population, min(coverage, 1.0), overlaps
    )


def aggregate_landcover(
    mesh: tuple[float, float, float, float], tile: Tile, counts: np.ndarray
) -> dict:
    """Area-weight class counts from 100 m cells; return class shares and mixedness."""
    if counts.ndim != 3 or counts.shape[:2] != tile.values.shape or np.any(counts < 0):
        raise ValueError("negative or malformed class-count raster")
    values = np.zeros(counts.shape[2], dtype=np.float64)
    coverage_area = 0.0
    col_start = max(0, math.floor((mesh[0] - tile.west) / tile.width))
    col_end = min(counts.shape[1], math.ceil((mesh[2] - tile.west) / tile.width))
    row_start = max(0, math.floor((tile.north - mesh[3]) / tile.height))
    row_end = min(counts.shape[0], math.ceil((tile.north - mesh[1]) / tile.height))
    for row in range(row_start, row_end):
        for col in range(col_start, col_end):
            cell = tile.cell_bounds(row, col)
            intersection = overlap_area(cell, mesh)
            if intersection <= 0:
                continue
            fraction = intersection / projected_area(cell)
            values += counts[row, col, :] * fraction
            coverage_area += intersection
    coverage = coverage_area / projected_area(mesh)
    if coverage > 1 + 1e-8:
        raise ValueError("land-cover cells overlap")
    total = float(values.sum())
    if total <= 0:
        return {
            "coverage": coverage,
            "shares": None,
            "mixedness": None,
            "valid_pixels": total,
        }
    shares = (values / total).tolist()
    return {
        "coverage": min(coverage, 1.0),
        "shares": shares,
        "mixedness": 1 - max(shares),
        "valid_pixels": total,
    }


def aggregate_census_rows(rows):
    """Sum prefecture × mesh rows, refusing suppression and malformed totals."""
    result = {}
    counts = {}
    input_rows = 0
    for prefecture, code, raw_population in rows:
        input_rows += 1
        if len(prefecture) != 2 or not prefecture.isdigit():
            raise ValueError(f"invalid prefecture: {prefecture!r}")
        mesh_bounds(code)
        if not raw_population.isascii() or not raw_population.isdigit():
            raise ValueError(
                f"invalid or suppressed total population: {raw_population!r}"
            )
        population = int(raw_population)
        result[code] = result.get(code, 0) + population
        counts[code] = counts.get(code, 0) + 1
    audit = {
        "input_rows": input_rows,
        "unique_meshes": len(result),
        "duplicate_mesh_codes": sum(n > 1 for n in counts.values()),
        "population_total": sum(result.values()),
    }
    return result, audit


def ranked_overlap(
    census: dict[str, float], estimate: dict[str, float], k: int
) -> dict:
    if census.keys() != estimate.keys() or k < 1 or k > len(census):
        raise ValueError("rankings require the same keys and 1 <= k <= n")
    census_top = sorted(census, key=lambda key: (-census[key], key))[:k]
    estimate_top = sorted(estimate, key=lambda key: (-estimate[key], key))[:k]
    overlap = len(set(census_top) & set(estimate_top))
    return {
        "census_top": census_top,
        "estimate_top": estimate_top,
        "overlap": overlap,
        "recall": overlap / k,
        "census_population_recovered": sum(census[key] for key in estimate_top)
        / sum(census[key] for key in census_top),
    }
