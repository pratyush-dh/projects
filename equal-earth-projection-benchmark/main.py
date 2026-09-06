#!/usr/bin/env python3
"""
Global Population Density Projection Comparison: Web Mercator vs Equal Earth
----------------------------------------------------------------------------
Author: Pratyush Dhungana
Description: Automatically verifies Python geospatial dependencies, fetches spatial data,
             calculates land-area and population density metrics, and generates a side-by-side
             visual comparison showing area distortion in Web Mercator vs Equal Earth.
"""

import sys
import subprocess
import importlib

# ---------------------------------------------------------------------------
# 1. DEPENDENCY CHECK & AUTOMATIC INSTALLATION
# ---------------------------------------------------------------------------
REQUIRED_PACKAGES = {
    "geopandas": "geopandas",
    "matplotlib": "matplotlib",
    "pyproj": "pyproj",
    "shapely": "shapely",
    "requests": "requests"
}

def check_and_install_dependencies():
    """Verify missing dependencies and auto-install via pip if necessary."""
    missing = []
    for pkg_import, pkg_pip in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(pkg_import)
        except ImportError:
            missing.append(pkg_pip)

    if missing:
        print(f"[!] Missing required packages: {missing}. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
            print("[+] All dependencies installed successfully.\n")
        except Exception as e:
            print(f"[-] Failed to auto-install dependencies: {e}")
            sys.exit(1)
    else:
        print("[+] All dependencies are already installed.\n")

check_and_install_dependencies()

# Import required libraries after dependency check
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap

# ---------------------------------------------------------------------------
# 2. DATA ACQUISITION & PREPROCESSING
# ---------------------------------------------------------------------------
def load_and_prepare_data():
    """Fetch low-resolution Natural Earth vector boundary dataset."""
    print("[*] Fetching world vector boundary data...")
    url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"

    try:
        world = gpd.read_file(url)
    except Exception as e:
        print(f"[-] Error downloading spatial vector dataset: {e}")
        sys.exit(1)

    # Filter out Antarctica for cleaner global layout
    world = world[world['CONTINENT'] != 'Antarctica'].copy()

    # Standardize population and country key names
    pop_col = 'POP_EST' if 'POP_EST' in world.columns else 'pop_est'

    # Project to Equal Earth (EPSG:8857) to compute accurate surface area
    world_eq = world.to_crs(epsg=8857)

    # Calculate area in km^2 (geometry.area returns m^2)
    world_eq['area_km2'] = world_eq.geometry.area / 1e6
    world_eq['pop_density'] = world_eq[pop_col] / world_eq['area_km2']

    return world_eq

# ---------------------------------------------------------------------------
# 3. SIDE-BY-SIDE PROJECTION VISUALIZATION
# ---------------------------------------------------------------------------
def generate_comparison_map(gdf):
    """Plot side-by-side comparison: Web Mercator vs Equal Earth."""
    print("[*] Generating comparative visualization...")

    # Reproject dataset into the two projections
    gdf_mercator = gdf.to_crs(epsg=3857)
    gdf_equal_earth = gdf.to_crs(epsg=8857)

    # Classification threshold bins (people / km^2)
    bounds = [0, 10, 25, 50, 100, 300, 1000, 15000]
    colors = ['#f7fcf5', '#e0f3db', '#ccece6', '#99d8c9', '#41ae76', '#238b45', '#005824']
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(bounds, cmap.N)

    # Setup 1x2 subplot layout
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
    fig.suptitle(
        'Global Population Density Mapping: Projection Distortion Comparison',
        fontsize=16,
        fontweight='bold',
        y=0.96
    )

    # Top Plot: Web Mercator (EPSG:3857)
    gdf_mercator.plot(
        column='pop_density',
        cmap=cmap,
        norm=norm,
        linewidth=0.3,
        edgecolor='#cccccc',
        ax=ax1
    )
    ax1.set_title(
        'Web Mercator (EPSG:3857) — High-Latitude Area Inflation (Conformal)',
        fontsize=12,
        pad=10
    )
    ax1.axis('off')

    # Bottom Plot: Equal Earth (EPSG:8857)
    gdf_equal_earth.plot(
        column='pop_density',
        cmap=cmap,
        norm=norm,
        linewidth=0.3,
        edgecolor='#cccccc',
        ax=ax2
    )
    ax2.set_title(
        'UN-Endorsed Equal Earth (EPSG:8857) — Accurate Area Proportions (Equal-Area)',
        fontsize=12,
        pad=10
    )
    ax2.axis('off')

    # Add shared colorbar at bottom
    cax = fig.add_axes([0.15, 0.06, 0.7, 0.02])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cax, orientation='horizontal')
    cbar.set_label('Population Density (people / km²)', fontsize=11, fontweight='medium')

    # Annotations
    plt.figtext(
        0.5, 0.01,
        'Data Source: Natural Earth Vector Data (1:110m) | Pipeline: GeoPandas & Matplotlib',
        ha='center',
        fontsize=9,
        color='gray'
    )

    # Save output plot image
    output_filename = "projection_comparison_map.png"
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"[+] Comparison map saved as '{output_filename}'")

    if sys.stdin.isatty():
        plt.show()

# ---------------------------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    world_gdf = load_and_prepare_data()
    generate_comparison_map(world_gdf)
