{ pkgs ? import <nixpkgs> {} }:

let
  espressif-qemu = pkgs.stdenv.mkDerivation {
    pname = "espressif-qemu";
    version = "9.2.2";

    src = pkgs.fetchurl {
      url = "https://github.com/espressif/qemu/releases/download/esp-develop-9.2.2-20261109/qemu-xtensa-softmmu-esp_develop_9.2.2_20261109-x86_64-linux-gnu.tar.xz";
      sha256 = "fbc3bffa9fa71192847969a627a584aabe2e86d85bed4902a096ff06c2b8a815";
    };

    nativeBuildInputs = [ pkgs.autoPatchelfHook ];
    buildInputs = with pkgs; [
      pixman
      libgcrypt
      SDL2
      zlib
      libslirp
      glib
    ];

    installPhase = ''
      mkdir -p $out
      cp -r * $out/
    '';
  };

  build = pkgs.writeShellScriptBin "build" ''
    exec pio run "$@"
  '';

  upload = pkgs.writeShellScriptBin "upload" ''
    exec pio run -t upload "$@"
  '';

  monitor = pkgs.writeShellScriptBin "monitor" ''
    exec pio device monitor "$@"
  '';

  flash = pkgs.writeShellScriptBin "flash" ''
    pio run -t upload "$@" && exec pio device monitor
  '';

  runtests = pkgs.writeShellScriptBin "runtests" ''
    exec ${pkgs.python3}/bin/python3 tests/run_tests.py "$@"
  '';

  mock = pkgs.writeShellScriptBin "mock" ''
    exec ${pkgs.python3}/bin/python3 tests/mock_server.py "$@"
  '';

  simulate = pkgs.writeShellScriptBin "simulate" ''
    set -e
    BUILD_DIR=".pio/build/ttgo_lora32_v21"
    if [ ! -f "$BUILD_DIR/firmware.bin" ]; then
      echo "Firmware bin not found. Building..."
      pio run
    fi
    echo "Creating unified 4MB flash image for QEMU..."
    ${pkgs.esptool}/bin/esptool --chip esp32 merge-bin -o "$BUILD_DIR/qemu_flash.bin" --pad-to-size 4MB \
      0x1000 "$BUILD_DIR/bootloader.bin" \
      0x8000 "$BUILD_DIR/partitions.bin" \
      0x10000 "$BUILD_DIR/firmware.bin"
    echo ""
    echo "============================================================"
    echo " Starting ESP32 QEMU Simulator (Press Ctrl+A then X to exit)"
    echo "============================================================"
    exec ${espressif-qemu}/bin/qemu-system-xtensa -nographic -machine esp32 \
      -drive file="$BUILD_DIR/qemu_flash.bin",if=mtd,format=raw -serial mon:stdio "$@"
  '';
in
pkgs.mkShell {
  name = "lilygo-433-dev-shell";

  buildInputs = with pkgs; [
    platformio
    git
    python3
    esptool
    build
    upload
    monitor
    flash
    runtests
    mock
    simulate
  ];

  shellHook = ''
    echo ""
    echo -e "\e[1;34m============================================================\e[0m"
    echo -e "\e[1;32m LilyGO LoRa32 433MHz — EMOS Weather Station Dev Shell\e[0m"
    echo -e "\e[1;34m============================================================\e[0m"
    echo -e "Dostupné zjednodušené příkazy:"
    echo -e "  \e[1;33mbuild\e[0m     - Přeloží firmware (pio run)"
    echo -e "  \e[1;33mupload\e[0m    - Nahraje firmware do připojené desky (pio run -t upload)"
    echo -e "  \e[1;33mmonitor\e[0m   - Otevře sériový monitor na 115200 baud (pio device monitor)"
    echo -e "  \e[1;33mflash\e[0m     - Přeloží, nahraje a rovnou spustí monitor"
    echo -e "  \e[1;33mruntests\e[0m  - Spustí automatické testy všech funkcí (python3 tests/run_tests.py)"
    echo -e "  \e[1;33mmock\e[0m      - Spustí lokální webový simulátor brány na portu 8080"
    echo -e "  \e[1;33msimulate\e[0m  - Spustí přeložený firmware v emulátoru QEMU ESP32"
    echo -e "\e[1;34m============================================================\e[0m"
    echo ""
  '';
}
