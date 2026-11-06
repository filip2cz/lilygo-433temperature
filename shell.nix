{ pkgs ? import <nixpkgs> {} }:

let
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
in
pkgs.mkShell {
  name = "lilygo-433-dev-shell";

  buildInputs = with pkgs; [
    platformio
    git
    build
    upload
    monitor
    flash
  ];

  shellHook = ''
    echo ""
    echo -e "\e[1;34m============================================================\e[0m"
    echo -e "\e[1;32m LilyGO LoRa32 433MHz — EMOS Weather Station Dev Shell\e[0m"
    echo -e "\e[1;34m============================================================\e[0m"
    echo -e "Dostupné zjednodušené příkazy:"
    echo -e "  \e[1;33mbuild\e[0m    - Přeloží firmware (pio run)"
    echo -e "  \e[1;33mupload\e[0m   - Nahraje firmware do připojené desky (pio run -t upload)"
    echo -e "  \e[1;33mmonitor\e[0m  - Otevře sériový monitor na 115200 baud (pio device monitor)"
    echo -e "  \e[1;33mflash\e[0m    - Přeloží, nahraje a rovnou spustí monitor"
    echo -e "\e[1;34m============================================================\e[0m"
    echo ""
  '';
}
