{pkgs}: {
  deps = [
    pkgs.xsimd
    pkgs.pkg-config
    pkgs.libxcrypt
    pkgs.docker-compose
    pkgs.postgresql
    pkgs.glibcLocales
  ];
}
