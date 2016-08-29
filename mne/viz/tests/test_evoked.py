# Authors: Alexandre Gramfort <alexandre.gramfort@telecom-paristech.fr>
#          Denis Engemann <denis.engemann@gmail.com>
#          Martin Luessi <mluessi@nmr.mgh.harvard.edu>
#          Eric Larson <larson.eric.d@gmail.com>
#          Cathy Nangini <cnangini@gmail.com>
#          Mainak Jas <mainak@neuro.hut.fi>
#          Jona Sassenhagen <jona.sassenhagen@gmail.com>
#
# License: Simplified BSD

import os.path as op
import warnings

import numpy as np
from numpy.testing import assert_raises


from mne import io, read_events, Epochs, pick_types, read_cov
from mne.channels import read_layout
from mne.utils import slow_test, run_tests_if_main
from mne.viz.evoked import _butterfly_onselect, plot_compare_evokeds
from mne.viz.utils import _fake_click

# Set our plotters to test mode
import matplotlib
matplotlib.use('Agg')  # for testing don't use X server

warnings.simplefilter('always')  # enable b/c these tests throw warnings


base_dir = op.join(op.dirname(__file__), '..', '..', 'io', 'tests', 'data')
evoked_fname = op.join(base_dir, 'test-ave.fif')
raw_fname = op.join(base_dir, 'test_raw.fif')
cov_fname = op.join(base_dir, 'test-cov.fif')
event_name = op.join(base_dir, 'test-eve.fif')
event_id, tmin, tmax = 1, -0.1, 0.1
n_chan = 6
layout = read_layout('Vectorview-all')


def _get_raw():
    return io.read_raw_fif(raw_fname, preload=False)


def _get_events():
    return read_events(event_name)


def _get_picks(raw):
    return pick_types(raw.info, meg=True, eeg=False, stim=False,
                      ecg=False, eog=False, exclude='bads')


def _get_epochs():
    raw = _get_raw()
    raw.add_proj([], remove_existing=True)
    events = _get_events()
    picks = _get_picks(raw)
    # Use a subset of channels for plotting speed
    picks = picks[np.round(np.linspace(0, len(picks) - 1, n_chan)).astype(int)]
    picks[0] = 2  # make sure we have a magnetometer
    with warnings.catch_warnings(record=True):  # proj
        epochs = Epochs(raw, events[:5], event_id, tmin, tmax, picks=picks,
                        baseline=(None, 0))
    epochs.info['bads'] = [epochs.ch_names[-1]]
    return epochs


def _get_epochs_delayed_ssp():
    raw = _get_raw()
    events = _get_events()
    picks = _get_picks(raw)
    reject = dict(mag=4e-12)
    epochs_delayed_ssp = Epochs(raw, events[:10], event_id, tmin, tmax,
                                picks=picks, baseline=(None, 0),
                                proj='delayed', reject=reject)
    return epochs_delayed_ssp


@slow_test
def test_plot_evoked():
    """Test plotting of evoked
    """
    import matplotlib.pyplot as plt
    evoked = _get_epochs().average()
    with warnings.catch_warnings(record=True):
        fig = evoked.plot(proj=True, hline=[1], exclude=[], window_title='foo')
        # Test a click
        ax = fig.get_axes()[0]
        line = ax.lines[0]
        _fake_click(fig, ax,
                    [line.get_xdata()[0], line.get_ydata()[0]], 'data')
        _fake_click(fig, ax,
                    [ax.get_xlim()[0], ax.get_ylim()[1]], 'data')
        # plot with bad channels excluded & spatial_colors & zorder
        evoked.plot(exclude='bads')
        evoked.plot(exclude=evoked.info['bads'], spatial_colors=True, gfp=True,
                    zorder='std')

        # test selective updating of dict keys is working.
        evoked.plot(hline=[1], units=dict(mag='femto foo'))
        evoked_delayed_ssp = _get_epochs_delayed_ssp().average()
        evoked_delayed_ssp.plot(proj='interactive')
        evoked_delayed_ssp.apply_proj()
        assert_raises(RuntimeError, evoked_delayed_ssp.plot,
                      proj='interactive')
        evoked_delayed_ssp.info['projs'] = []
        assert_raises(RuntimeError, evoked_delayed_ssp.plot,
                      proj='interactive')
        assert_raises(RuntimeError, evoked_delayed_ssp.plot,
                      proj='interactive', axes='foo')
        plt.close('all')

        # test GFP only
        evoked.plot(gfp='only')
        assert_raises(ValueError, evoked.plot, gfp='foo')

        evoked.plot_image(proj=True)
        # plot with bad channels excluded
        evoked.plot_image(exclude='bads', cmap='interactive')
        evoked.plot_image(exclude=evoked.info['bads'])  # does the same thing
        plt.close('all')

        evoked.plot_topo()  # should auto-find layout
        _butterfly_onselect(0, 200, ['mag', 'grad'], evoked)
        plt.close('all')

        cov = read_cov(cov_fname)
        cov['method'] = 'empirical'
        evoked.plot_white(cov)
        evoked.plot_white([cov, cov])

        # plot_compare_evokeds: test condition contrast, CI, color assignment
        plot_compare_evokeds(evoked.copy().pick_types(meg='mag'))
        evoked.rename_channels({'MEG 2142': "MEG 1642"})
        colors = dict(red='r', blue='b')
        linestyles = dict(red='--', blue='-')
        red, blue = evoked.copy(), evoked.copy()
        red.data *= 1.1
        blue.data *= 0.9
        plot_compare_evokeds([red, blue], picks=3)  # list of evokeds
        plot_compare_evokeds([[red, evoked], [blue, evoked]],
                             picks=3)  # list of lists
        # test picking & plotting grads
        contrast = dict()
        contrast["red/stim"] = list((evoked.copy(), red))
        contrast["blue/stim"] = list((evoked.copy(), blue))
        # test a bunch of params at once
        plot_compare_evokeds(contrast, colors=colors, linestyles=linestyles,
                             picks=[0, 2], vlines=[.01, -.04], invert_y=True,
                             truncate_yaxis=False, ymax=10, ymin=-10,
                             styles={"red/stim": {"linewidth": 1}})
        assert_raises(ValueError, plot_compare_evokeds,
                      contrast, picks='str')  # bad picks: not int
        assert_raises(ValueError, plot_compare_evokeds, evoked, picks=3,
                      colors=dict(fake=1))  # 'fake' not in conds
        assert_raises(ValueError, plot_compare_evokeds, evoked, picks=3,
                      styles=dict(fake=1))  # 'fake' not in conds
        assert_raises(TypeError, plot_compare_evokeds, evoked, picks=3,
                      ci='fake')  # ci must be float or None
        assert_raises(ValueError, plot_compare_evokeds, [[1, 2], [3, 4]],
                      picks=3)  # evoked must contain Evokeds
        contrast["red/stim"] = red
        contrast["blue/stim"] = blue
        plot_compare_evokeds(contrast, picks=[0], colors=['r', 'b'], ymax=0)

        # Hack to test plotting of maxfiltered data
        evoked_sss = evoked.copy()
        evoked_sss.info['proc_history'] = [dict(max_info=None)]
        evoked_sss.plot_white(cov)
        evoked_sss.plot_white(cov_fname)
        plt.close('all')
    evoked.plot_sensors()  # Test plot_sensors
    plt.close('all')

run_tests_if_main()
