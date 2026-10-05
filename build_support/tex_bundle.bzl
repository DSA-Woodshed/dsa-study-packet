"""Fetch the exact public TeX resource bytes used by the neutral packet."""

def _tex_resources_impl(rctx):
    lock = json.decode(rctx.read(rctx.attr.lock_file))
    resources = lock["resources"]

    # Small parallel batches avoid fetching the entire multi-gigabyte TeXLive
    # tar. Every response is checked against the independently recorded digest.
    for start in range(0, len(resources), 16):
        downloads = []
        for resource in resources[start:start + 16]:
            downloads.append(rctx.download(
                url = lock["url"],
                headers = {"Range": "bytes={}-{}".format(resource["offset"], resource["offset"] + resource["length"] - 1)},
                output = "resources/" + resource["name"],
                sha256 = resource["sha256"],
                canonical_id = lock["url"] + ":" + resource["name"],
                block = False,
            ))
        for download in downloads:
            download.wait()
    rctx.file("resources/SSOT", lock["origin_bundle_digest"])
    rctx.file("BUILD.bazel", """package(default_visibility = ["//visibility:public"])
exports_files(["resources/SSOT"])
filegroup(name = "files", srcs = glob(["resources/*"]))
""")

tex_resources = repository_rule(
    implementation = _tex_resources_impl,
    attrs = {"lock_file": attr.label(mandatory = True, allow_single_file = True)},
)
