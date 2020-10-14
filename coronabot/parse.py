import re
import dateparser

import constants
import location
import dateinterval


class Parser:
    """Abstract class for a generic Parser. Children classes must implement the methods `convert` and
    `mark_error`.
    Attributes:
        _result (any): conversion result, None by default
        status (bool): conversion status, True only if conversion was successful. If False, _result is not valid.
        error (str): error message associated to a failed conversion. Only valid if status is False.
    """

    def __init__(self):
        """Initialize Parser"""
        self._result = None
        self.status = False
        self.error = None

    @property
    def result(self):
        """Return conversion result only if status is true, otherwise raise an exception.
        Return:
            any: last conversion result
        Raise:
            Parser.ParserError: if status is false - some error occurred or conversion was never performed.
        """
        if self.status is True:
            return self._result
        else:
            raise Parser.ParserError("Cannot get results because an error occurred during conversion")

    def parse(self, string):
        """Parse a string using the convert and mark_error methods.
        Args:
            string (str): string to be parsed
        Return:
            bool: conversion status
        Raise:
            ParserError: if uncaught exceptions are raised
        """
        self.status = False
        try:
            result = self.convert(string)
        except Parser.ConversionError as e:
            self.status = False
            self.error = self.make_error_message(e, string)
        except Exception as e:
            self.status = False
            self.error = e.args
            raise Parser.ParserError(f"An error occurred during parsing") from e
        else:
            self._result = result
            self.status = True
        return self.status

    def convert(self, string):
        """Abstract method; must be overridden. Convert a string to its desired type or value.
        Args:
            string (str): string to be parsed, format is specific to the implemented
        Return:
            any
        """
        raise NotImplementedError()

    def make_error_message(self, error, string):
        """Generate the error message after a conversion failed and Parser.ConversionError was raised.
        Args:
            error (Parser.ConversionError): exception containing information about the error
            string (str): string that caused the error
        """
        raise NotImplementedError()

    def __bool__(self):
        """Mirror Parser status"""
        return self.status

    def __call__(self, *args, **kwargs):
        """Alias for `parse` method"""
        self.parse(*args, **kwargs)

    class ConversionError(Exception):
        """Exception for when the conversion fails for any reason"""
        pass

    class ParserError(Exception):
        """Exception for when, during conversion, other uncaught exceptions are raised"""
        pass


class ComposedParser(Parser):
    """Simplified interface for a nested parser.
    Attributes:
        subparsers (list): ordered list of Parser derived classes used to parse each field in a string
    """
    def __init__(self, subparsers):
        """Initialize instance
        Args:
            subparsers (list): ordered list of Parser derived classes used to parse each field in a string
        """
        super(ComposedParser, self).__init__()
        self.subparsers = subparsers

    def split(self, string):
        """Split composed string in a list of sub-strings. The size and the order of the returned list
        must correspond to the subparsers list.
        Args:
            string (str): string to split
        Return:
            list(str)
        """
        raise NotImplementedError()

    def convert(self, string):
        fields = self.split(string)
        if len(fields) != len(self.subparsers):
            raise Parser.ParserError(f"Cannot parse {len(fields)} fields with {len(self.subparsers)} parsers.")
        results = []
        for i, (field, parser) in enumerate(zip(fields, self.subparsers)):
            parser_instance = parser()
            partial_status = parser_instance.parse(field)
            if partial_status is False:
                raise Parser.ConversionError(i, field, parser_instance.error)
            results.append(parser_instance.result)
        return self.reduce(results)

    def reduce(self, partial_results):
        return partial_results

    def make_error_message(self, error, string):
        # Return the error message generated by the subparser that raised it
        return error.args[2]


class DateParser(Parser):
    """Date parser"""
    def convert(self, string):
        result = dateparser.parse(string, languages=['it', 'en'])
        if result is None:
            raise Parser.ConversionError(string)
        return result

    def make_error_message(self, error, string):
        return f"Non riconosco '{error.args[0]}' come una data valida. Prova ad utilizzare termini più semplici, " \
               f"come 'oggi', 'ieri', oppure insirisci la data per esteso come in '18 Luglio 2020'.\n\n" \
               f"Consulta /help per ulteriori informazioni."


class IntervalParser(ComposedParser):
    def __init__(self):
        super(IntervalParser, self).__init__([DateParser, DateParser])

    def split(self, string):
        _, interval, _ = re.split(f"({constants.interval})", string)
        _, sdate, edate, _ = re.split(fr"({constants.date})\s?-\s?({constants.date})", interval)
        return [sdate, edate]

    def reduce(self, partial_results):
        return dateinterval.DateInterval(*partial_results)


class LocationParser(Parser):
    def convert(self, string):
        string = location.Location.resolve_alias(string, constants.location_aliases)
        if string == constants.country:
            return location.Location(string, 'stato')
        elif string in constants.regions:
            return location.Location(string, 'regione')
        elif string in constants.provinces:
            return location.Location(string, 'provincia')
        else:
            raise Parser.ConversionError(string)

    def make_error_message(self, error, string):
        #TODO: suggest similar locations
        return f"Non riconosco '{string}' come un luogo valido. Prova con il nome di una provincia, di una regione o " \
               f"con 'Italia'.\n\nConsulta /help per ulteriori informazioni."


class StatParser(Parser):
    def convert(self, string):
        result = string.replace(' ', '_')
        if result not in constants.stats.keys():
            raise Parser.ConversionError(string)
        return string.replace(' ', '_')

    def make_error_message(self, error, string):
        return f"Non riconosco '{string}' come una statistica valida."


class ReportRequestParser(ComposedParser):
    REQUEST_PATTERN = constants.report_request

    def __init__(self):
        super(ReportRequestParser, self).__init__([LocationParser, DateParser])

    def split(self, string):
        _, location, date, _ = re.split(ReportRequestParser.REQUEST_PATTERN, string)
        if date is None:
            date = 'oggi'
        return location, date


class TrendRequestParser(ComposedParser):
    REQUEST_PATTERN = constants.trend_request

    def __init__(self):
        super(TrendRequestParser, self).__init__([StatParser, LocationParser, IntervalParser])

    def split(self, string):
        _, stat, location, interval, _ = re.split(TrendRequestParser.REQUEST_PATTERN, string)
        if location is None:
            location = 'italia'
        if interval is None:
            interval = '24/02/2020 - oggi'
        return stat, location, interval