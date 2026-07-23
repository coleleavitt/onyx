from fastapi.routing import APIRoute

from onyx.server.features.projects.api import router


def _route_index(path: str, method: str) -> int:
    for index, route in enumerate(router.routes):
        if (
            isinstance(route, APIRoute)
            and route.path == path
            and method in route.methods
        ):
            return index
    raise AssertionError(f"Route {method} {path} not found")


def test_connected_source_collection_routes_precede_dynamic_project_route() -> None:
    dynamic_project_get = _route_index("/user/projects/{project_id}", "GET")

    assert (
        _route_index("/user/projects/connected-source-scopes", "GET")
        < dynamic_project_get
    )
    assert (
        _route_index("/user/projects/connected-knowledge-presets", "GET")
        < dynamic_project_get
    )
    assert (
        _route_index("/user/projects/connected-knowledge-presets", "POST")
        < dynamic_project_get
    )


def _first_matching_route_path(path: str, method: str) -> str:
    for route in router.routes:
        if not isinstance(route, APIRoute) or method not in route.methods:
            continue
        match, _ = route.matches({"type": "http", "method": method, "path": path})
        if match.name == "FULL":
            return route.path
    raise AssertionError(f"No route matched {method} {path}")


def test_collection_paths_match_collection_routes_before_dynamic_project_route() -> (
    None
):
    assert (
        _first_matching_route_path("/user/projects/connected-source-scopes", "GET")
        == "/user/projects/connected-source-scopes"
    )
    assert (
        _first_matching_route_path("/user/projects/connected-knowledge-presets", "GET")
        == "/user/projects/connected-knowledge-presets"
    )
    assert (
        _first_matching_route_path("/user/projects/connected-knowledge-presets", "POST")
        == "/user/projects/connected-knowledge-presets"
    )
