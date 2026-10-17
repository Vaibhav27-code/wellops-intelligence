import React from 'react';
import type { VisualizationSpec } from '../../types';
import { LeafletMapInner } from './LeafletMapInner';
import { DataTable } from './DataTable';

interface MapVizProps {
  spec: VisualizationSpec;
}

interface MapVizState {
  hasError: boolean;
}

export class MapViz extends React.Component<MapVizProps, MapVizState> {
  constructor(props: MapVizProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.warn('MapViz caught error, falling back to data table:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="map-viz map-error-fallback">
          <p style={{ fontSize: '12px', color: 'var(--c-text-muted)', marginBottom: '8px' }}>
            Map rendering encountered an issue — falling back to data table:
          </p>
          <DataTable spec={this.props.spec} />
        </div>
      );
    }

    return <LeafletMapInner spec={this.props.spec} />;
  }
}
