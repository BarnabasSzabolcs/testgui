/* global _, Vue */

const failedStatuses = ['error', 'failure']

function getLeaves (tree) {
  if (tree.children === undefined) {
    return [tree]
  }
  const leaves = tree.children.map(child => getLeaves(child))
  return _.flatten(leaves)
}

Vue.component('display-status', {
  props: ['status', 'size'],
  template: `
    <div class="single-line">
      <div v-if="displayDetails" class="inline-block" style="opacity: 0.8">
        <span v-for="(count, statusName) of status" :class="statusName | statusColor">
          {{ count }}
        </span>
      </div>
      <div class="inline-block" :class="{'q-mr-xs': displaySpinner && !size}">
        <q-spinner 
            v-if="displaySpinner" 
            @click="$emit('run')" 
            :size="size"
        ></q-spinner>
        <q-icon
            v-else
            :size="size"
            :class="displayIconStatus | statusColor"
            :name="displayIconStatus | statusIcon"
            @click="$emit('run')"
            class="clickable"></q-icon>
      </div>
    </div>
    `,
  filters: {
    statusIcon: function (status) {
      return {
        run: 'play_arrow',
        notRun: 'play_arrow',
        success: 'done',
        error: 'error',
        failure: 'highlight_off'
      }[status]
    },
    statusColor: function (status) {
      return {
        run: 'text-black',
        notRun: 'text-black',
        success: 'text-positive',
        error: 'text-warning',
        failure: 'text-negative'
      }[status]
    }
  },
  computed: {
    displayDetails () {
      if (_.isString(this.status)) {
        return false
      }
      return true
    },
    displayIconStatus () {
      if (_.isString(this.status)) { return this.status }
      if ('running' in this.status) { return 'running' }
      if ('notRun' in this.status) { return 'notRun' }
      if ('error' in this.status) { return 'error' }
      if ('failure' in this.status) { return 'failure' }
      if ('success' in this.status) { return 'success' }
      return 'notRun'
    },
    displaySpinner () {
      return this.displayIconStatus === 'running'
    }
  }
})

// eslint-disable-next-line no-unused-vars
const app = new Vue({
  el: '#q-app',
  data: function () {
    return {
      allNodes: [],
      testTree: [],
      tests: {},
      expandProblems: true,
      reloadModules: true,
      loadingTests: true,

      ticked: [],
      selected: '',
      expanded: [],
      filter: '',
      splitterModel: 40
    }
  },
  computed: {
    anyTestRunning () {
      return _.some(this.tests, test => test.status === 'running')
    },
    allSuccess () {
      return this.nStatuses.success > 0 && _.keys(this.nStatuses).length === 1
    },
    nStatuses () {
      return _.countBy(this.tests, test => test.status)
    },
    selectedTests () {
      const selectedNode = this.allNodes[this.selected]
      if (selectedNode === undefined) { return _.filter(this.tests, test => failedStatuses.includes(test.status)) }
      if (selectedNode.children === undefined) { return [selectedNode] }
      return getLeaves(selectedNode)
    }
  },
  watch: {
    expandProblems: function (expand) {
      _.each(this.tests, test => {
        this.$set(test, 'expand', expand ? failedStatuses.includes(test.status) : undefined)
      })
    }
  },
  methods: {
    repopulateTests () {
      this.allNodes = {}
      this.tests = {}
      this.testTree = []
      this.loadingTests = true
      window.pywebview.api.repopulate_tests()
    },
    runAllTests () {
      _.each(this.tests, t => {
        t.status = 'running'
      })
      window.pywebview.api.run_all_tests()
    },
    runSelectedTests () {
      this.runTests(this.ticked.map(name => this.tests[name]))
    },
    runFailedTests () {
      const failedTests = _.filter(this.tests, test => failedStatuses.includes(test.status))
      this.runTests(failedTests)
    },
    runTestsForNode (node) {
      const tests = getLeaves(node)
      this.runTests(tests)
    },
    runTests (tests) {
      _.each(tests, t => {
        this.setTestStatus(t, 'running')
      })
      window.pywebview.api.run_selected_tests(
        _.map(tests, test => test.index)
      )
    },
    setTestStatus (test, status) {
      console.log('test:', test.label)
      if (test.children === undefined) {
        // I'm a leaf, set my status
        this.$set(test, 'status', status)
        if (this.expandProblems) {
          this.$set(test, 'expand', ['error', 'failure'].includes(test.status))
        }
      } else {
        // I'm a parent, my status only depends on my children
        const leafChildren = _.filter(test.children, child => _.isString(child.status))
        const leafStatuses = _.countBy(leafChildren, child => child.status)
        const nonLeafChildren = _.filter(test.children, child => !_.isString(child.status))
        const statuses = _.map(nonLeafChildren, child => child.status)
        statuses.push(leafStatuses)
        const status = statuses.reduce((acc, statuses) => {
          _.each(statuses, (v, k) => { k in acc ? acc[k] += v : acc[k] = v })
          return acc
        }, {})
        this.$set(test, 'status', status)
      }
      const path = test.label.split('.')
      path.pop()
      const parent = this.allNodes[path.join('.')]
      if (parent !== undefined) {
        // set my parents status walking up the structure
        this.setTestStatus(parent)
      }
    },
    resetFilter () {
      this.filter = ''
      this.$refs.filter.focus()
    },

    // functions called by the backend
    initTests (tests) {
      this.$set(this, 'allNodes', {})
      this.$set(this, 'tests', {})
      this.$set(this, 'testTree', [])

      tests.forEach((path, i) => {
        const { tree, name } = path.reduce(({ tree, name }, pathComponent) => {
          let children
          if (_.isArray(tree)) {
            children = tree
          } else {
            tree.children = tree.children || []
            children = tree.children
          }
          if (name) { name += '.' }
          name += pathComponent
          const existing = _.filter(children, child => child.label === name)
          if (existing.length) {
            return { tree: existing[0], name }
          }
          const leaf = {
            title: pathComponent,
            label: name,
            status: 'notRun'
          }
          this.allNodes[name] = leaf
          children.push(leaf)
          return { tree: leaf, name }
        }, { tree: this.testTree, name: '' })
        const test = tree
        test.index = i
        this.$set(this.tests, name, test)
      })
      _.each(this.allNodes, (node, name) => { this.expanded.push(name) })
      this.loadingTests = false
    },
    setResult ({ name, message, status }) {
      this.setTestStatus(this.tests[name], status)
      this.tests[name].message = message
    },
    setWarning ({ message }) {
      const longTimeOut = 7000
      this.$q.notify({
        type: 'warning',
        timeout: longTimeOut,
        position: 'top',
        message: message,
        multiline: true
      })
    }
  }
})
