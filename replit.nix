{pkgs}: {
  deps = [
    pkgs.docker-compose
    pkgs.postgresql
    pkgs.glibcLocales
  ];
}
