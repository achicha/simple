import pandas as pd
import numpy as np
import re
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from inspect import getfullargspec
from itertools import repeat, zip_longest
from ipywidgets import widgets, interactive, HBox, VBox
from plotly_resampler import FigureWidgetResampler
from ipyslickgrid import show_grid


default_template = 'plotly_white'


def addLines(fig: go.FigureWidget, **line_styles):
    """Add line (or lines) to the figure"""

    for line_name in line_styles:
        line = line_styles[line_name]
        if type(line) != dict:
            line = {'hf_y': line}  # if there is only one value specified - interpret as Y series

        line_class = go.scattergl.Marker if line.get('mode') == 'markers' else go.scattergl.Line
        trace_dict = {}  # parameters not belong to the Line will be moved to upper-levels
        scatter_dict = {}
        line_dict = {}
        for param in line:
            if param in getfullargspec(line_class).args:
                line_dict[param] = line[param]
            elif param in getfullargspec(go.Scattergl).args:
                scatter_dict[param] = line[param]
            else:
                trace_dict[param] = line[param]

        scatter_dict['marker' if line_class == go.scattergl.Marker else 'line'] = line_dict
        if 'row' in trace_dict and 'col' not in trace_dict:
            trace_dict['col'] = 1
        fig.add_trace(go.Scattergl(name=line_name, **scatter_dict), limit_to_view=True, **trace_dict)


def chartFigure(height: int = 700, rows: int = 1, template: str = default_template, **lines) -> go.FigureWidget:
    """Create default chart widget with horizontal subplots"""

    specs = [[{"secondary_y": True}] for _ in range(rows)]
    if rows > 1:
        k = (0.1 + 0.1 * rows)
        row_heights = [1 - k] + list(repeat(k / (rows - 1), rows - 1))
    else:
        row_heights = None

    fig = FigureWidgetResampler(
        go.FigureWidget(make_subplots(rows=rows, cols=1, row_heights=row_heights,
                                      vertical_spacing=0.03, shared_xaxes=True, specs=specs)))

    fig.update_layout(autosize=True, height=height, template=template,
                      legend=dict(x=0.1, y=1, orientation="h"),
                      margin=dict(l=45, r=15, b=10, t=30, pad=3))

    if lines is not None:
        addLines(fig, **lines)

    fig.update_xaxes(spikemode='across+marker', spikedash='dot', spikethickness=2, spikesnap='cursor')
    fig.update_traces(xaxis=f'x{rows}')

    return fig


def updateLines(fig: go.FigureWidget, **line_data):
    """Update lines xy-values"""

    # strip html tags and some others auxiliary marks
    names = [re.sub('<[^<]+?>|\[.*]|~.*|\s', '', s.name) for s in fig.data]
    with fig.batch_update():
        for line_name in filter(lambda name: name in names, line_data):
            k = names.index(line_name)
            line = line_data[line_name]
            if type(line) == dict:
                fig.hf_data[k]['x'] = line['x']
                fig.hf_data[k]['y'] = line['y']
            else:
                fig.hf_data[k]['x'] = np.arange(len(line))
                fig.hf_data[k]['y'] = line

        fig.reload_data()


def updateSliders(sliders: widgets, **values: dict):
    """Update slider values"""

    for slider in sliders:
        slider.value = values[slider.description]


def interactFigure(model: callable, line_styles: dict,
                   height: int = 700, rows: int = 1, template: str = default_template) -> widgets:
    """Interactive chart with model's internal data-series and sliders to change parameters"""

    spec = getfullargspec(model)
    x = dict(zip_longest(reversed(spec.args), [] if spec.defaults is None else reversed(spec.defaults), fillvalue=1))
    defaults = dict(reversed(x.items()))
    fig = chartFigure(height=height, rows=rows, template=template, **line_styles)

    def update(**arg):
        updateLines(fig, **model(**arg)[1])

    sliders = interactive(update, **defaults).children[:-1]

    # first run with initial values
    param = {s.description: s.value for s in sliders}
    update(**param)

    return VBox([HBox(sliders), fig])


def interactTable(model: callable, line_styles: dict, X: pd.DataFrame,
                  height: int = 700, rows: int = 1, template: str = default_template) -> widgets:
    """Interactive parameter table browser"""

    box = interactFigure(model, line_styles, height=height, rows=rows, template=template)

    def on_changed(event, grid):
        changed = grid.get_changed_df()
        k = event['new'][0]
        selected = changed.iloc[k:k + 1].to_dict('records')[0]
        param = dict(filter(lambda x: x[0] in getfullargspec(model).args, selected.items()))

        sliders = box.children[0].children
        updateSliders(sliders, **param)

        fig = box.children[1]
        updateLines(fig, **model(**param)[1])

    grid = show_grid(X, grid_options={'editable': False, 'forceFitColumns': True, 'multiSelect': False},
                     column_options={'defaultSortAsc': False})
    grid.on('selection_changed', on_changed)

    return VBox([box, grid])


def chartParallel(X: pd.DataFrame, height: int = 400) -> widgets:
    """Parallel coordinates plot for optimization results"""
    fig = go.FigureWidget(data=go.Parcoords(dimensions=[{'label': c, 'values': X[c]} for c in X.columns]))
    fig.update_layout(autosize=True, height=height, template=default_template, margin=dict(l=45, r=45, b=20, t=50, pad=3))
    return fig

