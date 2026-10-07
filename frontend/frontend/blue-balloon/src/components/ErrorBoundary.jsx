import React from 'react';
export class ErrorBoundary extends React.Component {
  state = {error: null};
  static getDerivedStateFromError(error) {return {error};}
  render() {if (this.state.error) return <main className="status-page"><h1>We couldn’t open this workspace</h1><p>Your saved book has not been removed. Reload to try again.</p><button className="ui-btn ui-btn--default" onClick={() => location.reload()}>Reload workspace</button><a href="/home">Back to your books</a></main>; return this.props.children;}
}
