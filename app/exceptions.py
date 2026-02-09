"""Custom exceptions for Project Hermes."""


class HermesException(Exception):
    """Base exception for Project Hermes."""
    pass


class RouteNotFoundError(HermesException):
    """Route with given ID was not found."""
    pass


class InvalidAreaError(HermesException):
    """Invalid or unknown hiking area."""
    pass


class RoutingError(HermesException):
    """Error during route calculation."""
    pass


class GraphNotFoundError(HermesException):
    """Graph for given area not found or not built."""
    pass


class ElevationDataError(HermesException):
    """Error fetching or processing elevation data."""
    pass


class InvalidRouteParametersError(HermesException):
    """Invalid route planning parameters."""
    pass


class NoValidPathError(RoutingError):
    """No valid path found between given points."""
    pass
