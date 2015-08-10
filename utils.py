__author__ = 'nickdg'

import experiment as exp

def draw_graph(experiment):
    """draws the state branches of all trials in an experiment as a graph to a .png file.
    Requires that graphviz-dev and pygraphviz are installed."""

    import pygraphviz as pgv

    for trial in experiment.conditions:

        # Create Graphviz graph
        graph = pgv.AGraph(directed=True)

        # Create a more informative label (graph_name) for each state's node.
        # TODO: Make the Parameter labeling process more clean and reliable.

        for state in trial.branches:
            has_val = False
            for param in state.params_in:
                if isinstance(param, exp.Var):
                    state.graph_name = str(state) + '\n' + str((param.values[trial],))
                    state.graph_fontcolor = 'red'
                    has_val = True
            if not has_val:
                state.graph_name = str(state) + '\n' + str(state.params_in)
                state.graph_fontcolor = 'black'

        # Draw Nodes
        for state in trial.branches:
            if isinstance(state, exp.TimerState):
                shape = 'ellipse'
            elif isinstance(state, exp.EndState):
                shape = 'diamond'
            else:
                shape = 'box'

            graph.add_node(state.graph_name, shape=shape, fontcolor=state.graph_fontcolor)

        # Draw Edges
        for state in trial.branches:
            if len(trial.branches[state].keys()) == 1:
                style = 'solid'
            else:
                style = 'dotted'
            for edge in trial.branches[state]:
                graph.add_edge(state.graph_name, trial.branches[state][edge].graph_name, style=style, label=str(edge))

        graph.layout('dot')  # Vertical layout.

        file_name = experiment.name + '_' + str(trial) + '.png'
        graph._draw(file_name)