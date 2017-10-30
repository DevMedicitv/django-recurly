
import six
import recurly.errors

# these errors don't have proper python3 compatibility

def validationerror__unicode__(self):
    all_error_strings = []
    for error in self.errors.values():
        if isinstance(error, (tuple, list)):
            all_error_strings += [six.text_type(e) for e in error]  # multiple errors on field
        else:
            all_error_strings.append(six.text_type(error))
    return six.u('; ').join(all_error_strings)

def suberror__str__(self):
    return self.__unicode__()

recurly.errors.ValidationError.__unicode__ = validationerror__unicode__
recurly.errors.ValidationError.Suberror.__str__ = suberror__str__
