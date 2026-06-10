#!/data/data/com.termux/files/usr/bin/bash
#==============================================================================
#  HARMESH TRADING SYSTEM — Unified Auto-Start Entry Point
#  ./start.sh  →  boots the full harmonized trading system
#==============================================================================
set -e

HARMESH_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$HARMESH_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

#--------------------------------------------------------------
# 1. Verify environment
#--------------------------------------------------------------
echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            HARMESH TRADING SYSTEM v1.0                      ║"
echo "║            Crypto Trading Bot for Termux/Android             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python $(python3 --version 2>&1)"

# Check virtual environment
if [ ! -f "$HARMESH_DIR/venv/bin/activate" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m virtualenv venv
fi

# Activate venv
source "$HARMESH_DIR/venv/bin/activate" 2>/dev/null || source "$HARMESH_DIR/venv/bin/activate"

# Verify key packages
echo -n "Checking dependencies..."
python3 -c "import ccxt, pandas, rich, ta" 2>/dev/null && \
    echo -e "${GREEN} OK${NC}" || {
    echo -e "\n${YELLOW}Installing dependencies...${NC}"
    pip install -q ccxt pandas numpy ta rich tabulate requests pyyaml python-dotenv
}

#--------------------------------------------------------------
# 2. Check config.json
#--------------------------------------------------------------
if [ ! -f "$HARMESH_DIR/config.json" ]; then
    echo -e "${RED}ERROR: config.json not found${NC}"
    echo "Run: cp config.example.json config.json"
    exit 1
fi
echo -e "${GREEN}✓${NC} config.json loaded"

#--------------------------------------------------------------
# 3. Create essential directories
#--------------------------------------------------------------
mkdir -p "$HARMESH_DIR/logs" "$HARMESH_DIR/data"
echo -e "${GREEN}✓${NC} Directories ready"

#--------------------------------------------------------------
# 4. Display system info
#--------------------------------------------------------------
echo ""
echo -e "${BOLD}System Info:${NC}"
echo "  Home:     $HARMESH_DIR"
echo "  Python:   $(python3 --version 2>&1)"
echo "  Platform: $(uname -o) on $(uname -m)"
echo "  Free RAM: $(free -h 2>/dev/null | awk '/Mem:/{print $4}' || echo 'N/A')"
echo "  Free Disk: $(df -h . | tail -1 | awk '{print $4}')"
echo ""

# Detect installed frameworks
if [ -d "$HARMESH_DIR/freqtrade" ]; then
    echo -e "${GREEN}✓${NC} freqtrade repository found"
fi
if [ -d "$HARMESH_DIR/ccxt" ]; then
    echo -e "${GREEN}✓${NC} CCXT source found"
fi

#--------------------------------------------------------------
# 5. Check Phase 1 → Phase 2 status
#--------------------------------------------------------------
echo ""
echo -e "${BOLD}Checking upgrade status...${NC}"
python3 "$HARMESH_DIR/main.py" --check-upgrade 2>/dev/null || echo ""

#--------------------------------------------------------------
# 6. Launch interactive menu
#--------------------------------------------------------------
echo ""
echo -e "${CYAN}${BOLD}Select mode:${NC}"
echo "  1) Paper Trading (Phase 1 — virtual \$1000)"
echo "  2) Live Trading (Phase 2 — real money)"
echo "  3) Show Status Dashboard"
echo "  4) Reset Paper Trading State"
echo "  5) Exit"
echo ""
read -p "Choice [1-5]: " choice

case "$choice" in
    1)
        echo -e "\n${GREEN}Starting Paper Trading — Phase 1${NC}"
        interval=${HARMESH_TICK_INTERVAL:-300}
        python3 "$HARMESH_DIR/main.py" --mode paper --interval "$interval"
        ;;
    2)
        echo -e "\n${YELLOW}Starting Live Trading — Phase 2${NC}"
        interval=${HARMESH_TICK_INTERVAL:-300}
        python3 "$HARMESH_DIR/main.py" --mode live --interval "$interval"
        ;;
    3)
        python3 "$HARMESH_DIR/main.py" --status
        echo ""
        read -p "Press Enter to return to menu..."
        exec "$0"
        ;;
    4)
        echo -e "\n${RED}Resetting paper trading state...${NC}"
        python3 "$HARMESH_DIR/main.py" --reset
        echo -e "${GREEN}Done.${NC}"
        read -p "Press Enter to return to menu..."
        exec "$0"
        ;;
    5|*)
        echo -e "${CYAN}Goodbye!${NC}"
        exit 0
        ;;
esac
